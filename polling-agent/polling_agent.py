#!/usr/bin/env python3
import os
import json
import time
import re
import boto3
import requests
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# 환경 변수
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-2')
AMPLIFY_BACKEND_URL = os.getenv('AMPLIFY_BACKEND_URL')
KNATIVE_NAMESPACE = os.getenv('KNATIVE_NAMESPACE', 'user-functions')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))  # 10초마다 polling

# Kubernetes 클라이언트 초기화
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

k8s_custom = client.CustomObjectsApi()
k8s_core = client.CoreV1Api()

# SQS 클라이언트 초기화 (EC2 IAM Role 사용)
sqs = boto3.client('sqs', region_name=AWS_REGION)

def validate_input(user_id, custom_routes):
    """
    userId와 customRoutes 입력 검증
    - 알파벳, 숫자, 하이픈(-), 언더스코어(_)만 허용
    - URI 특수문자 (/, ?, &, =, #, % 등) 금지
    """
    # Kubernetes 리소스 이름 규칙: 소문자 알파벳, 숫자, 하이픈만 허용
    valid_pattern = re.compile(r'^[a-zA-Z0-9\-_]+$')

    errors = []

    if not valid_pattern.match(user_id):
        errors.append(f"userId contains invalid characters: '{user_id}' (only alphanumeric, hyphen, underscore allowed)")

    if not valid_pattern.match(custom_routes):
        errors.append(f"customRoutes contains invalid characters: '{custom_routes}' (only alphanumeric, hyphen, underscore allowed)")

    # 특별히 URI 특수문자 체크
    uri_special_chars = ['/', '?', '&', '=', '#', '%', '+', ' ', '@', '!', '*', '(', ')']
    for char in uri_special_chars:
        if char in user_id:
            errors.append(f"userId contains forbidden URI character: '{char}'")
            break
        if char in custom_routes:
            errors.append(f"customRoutes contains forbidden URI character: '{char}'")
            break

    return len(errors) == 0, errors

def create_knative_service(user_id, function_id, custom_routes, ecr_image):
    """
    Knative Service 생성 또는 업데이트
    - 기존 서비스가 있으면 patch로 업데이트
    - 없으면 새로 생성
    - 이름: {userid}-{customroutes}
    - 레이블: functionId, userId
    """
    service_name = f"{user_id}-{custom_routes}".lower()

    knative_service = {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": service_name,
            "namespace": KNATIVE_NAMESPACE,
            "labels": {
                "functionId": function_id,
                "userId": user_id,
                "customRoutes": custom_routes,
                "managed-by": "polling-agent"
            }
        },
        "spec": {
            "template": {
                "metadata": {
                    "labels": {
                        "functionId": function_id,
                        "userId": user_id
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "image": ecr_image,
                            "ports": [
                                {
                                    "containerPort": 8080
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }

    try:
        # Knative Service 생성 또는 업데이트 (patch 사용)
        k8s_custom.patch_namespaced_custom_object(
            group="serving.knative.dev",
            version="v1",
            namespace=KNATIVE_NAMESPACE,
            plural="services",
            name=service_name,
            body=knative_service
        )
        print(f"✓ Knative Service '{service_name}' created/updated successfully")
        return True
    except ApiException as e:
        if e.status == 404:
            # 리소스가 없으면 생성
            print(f"! Knative Service '{service_name}' not found, creating...")
            try:
                k8s_custom.create_namespaced_custom_object(
                    group="serving.knative.dev",
                    version="v1",
                    namespace=KNATIVE_NAMESPACE,
                    plural="services",
                    body=knative_service
                )
                print(f"✓ Knative Service '{service_name}' created successfully")
                return True
            except Exception as create_error:
                print(f"✗ Failed to create Knative Service: {create_error}")
                return False
        else:
            print(f"✗ Failed to patch Knative Service: {e}")
            return False

def wait_for_revision_ready(service_name, timeout=60):
    """
    Knative Revision이 Ready 상태가 될 때까지 대기
    - latestReadyRevisionName이 존재하는지 체크
    - Revision이 없으면 배포 실패 (이미지 pull 실패, crash 등)
    """
    start_time = time.time()
    check_count = 0

    print(f"  Waiting for Revision to be ready (timeout: {timeout}s)")

    while time.time() - start_time < timeout:
        check_count += 1
        elapsed = int(time.time() - start_time)
        print(f"  [Check #{check_count}] Elapsed: {elapsed}s / {timeout}s")

        try:
            service = k8s_custom.get_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=KNATIVE_NAMESPACE,
                plural="services",
                name=service_name
            )

            # latestReadyRevisionName 확인
            latest_ready = service.get('status', {}).get('latestReadyRevisionName')
            latest_created = service.get('status', {}).get('latestCreatedRevisionName')

            if latest_ready:
                print(f"✓ Revision '{latest_ready}' is Ready")
                url = service.get('status', {}).get('url', '')
                return True, url

            # Revision이 생성되었지만 Ready가 아닌 경우
            if latest_created and not latest_ready:
                print(f"  Revision '{latest_created}' created but not ready yet...")
                # ConfigurationsReady condition 체크
                conditions = service.get('status', {}).get('conditions', [])
                config_ready = next((c for c in conditions if c['type'] == 'ConfigurationsReady'), None)
                if config_ready and config_ready.get('status') == 'False':
                    reason = config_ready.get('reason', 'Unknown')
                    message = config_ready.get('message', '')
                    print(f"  Configuration not ready - Reason: {reason}, Message: {message}")

        except ApiException as e:
            print(f"  Error checking service status: {e}")

        print(f"  Sleeping 5 seconds before next check...")
        time.sleep(5)

    print(f"✗ Timeout: Revision not ready after {timeout}s")
    return False, None

def wait_for_ingress_ready(service_name, timeout=30):
    """
    Knative Service의 Ingress가 Ready 상태가 될 때까지 대기
    (현재는 사용하지 않음 - Nginx + Kourier Internal 아키텍처에서는 IngressReady가 항상 Unknown)
    """
    start_time = time.time()
    check_count = 0

    print(f"  Starting readiness check for '{service_name}' (timeout: {timeout}s)")

    while time.time() - start_time < timeout:
        check_count += 1
        elapsed = int(time.time() - start_time)
        print(f"  [Check #{check_count}] Elapsed: {elapsed}s / {timeout}s")

        try:
            service = k8s_custom.get_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=KNATIVE_NAMESPACE,
                plural="services",
                name=service_name
            )

            # Status conditions 확인
            conditions = service.get('status', {}).get('conditions', [])
            ready_condition = next((c for c in conditions if c['type'] == 'Ready'), None)

            if ready_condition and ready_condition['status'] == 'True':
                url = service.get('status', {}).get('url', '')
                print(f"✓ Knative Service '{service_name}' is Ready. URL: {url}")
                return True, url

            # IngressNotConfigured 등의 에러 체크
            if ready_condition and ready_condition['status'] == 'False':
                reason = ready_condition.get('reason', 'Unknown')
                message = ready_condition.get('message', '')
                print(f"  Status: Not Ready | Reason: {reason} | Message: {message}")
            else:
                print(f"  Status: Waiting for Ready condition...")

        except ApiException as e:
            print(f"  Error checking service status: {e}")

        print(f"  Sleeping 5 seconds before next check...")
        time.sleep(5)

    print(f"✗ Timeout waiting for Knative Service '{service_name}' to become ready after {check_count} checks")
    return False, None

def send_result_to_amplify(user_id, function_id, custom_routes, success, message, url=None, image_digest=None):
    """
    Amplify 백엔드에 결과 전송
    /api/deploy/success 또는 /api/deploy/failed
    """
    endpoint = f"{AMPLIFY_BACKEND_URL}/api/deploy/{'success' if success else 'failed'}"

    payload = {
        "userId": user_id,
        "functionId": function_id,
        "customRoutes": custom_routes,
        "message": message,
        "url": url,
        "imageDigest": image_digest,
        "timestamp": int(time.time())
    }

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 200:
            print(f"✓ Result sent to Amplify backend successfully: {endpoint}")
            return True
        else:
            print(f"✗ Failed to send result to Amplify: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error sending result to Amplify: {e}")
        return False

def process_message(message):
    """
    SQS 메시지 처리
    """
    try:
        # 메시지 파싱
        body = json.loads(message['Body'])
        user_id = body.get('userId') or body.get('userId')
        function_id = body.get('functionId') or body.get('FunctionID')
        custom_routes = body.get('customRoutes') or body.get('CustomRoutes')
        ecr_image = body.get('imageDigest') or body.get('ImageDigest')

        if not all([user_id, function_id, custom_routes, ecr_image]):
            print(f"✗ Missing required fields in message: {body}")
            # 필드가 있는 것만 사용해서 실패 알림 전송
            if user_id and function_id and custom_routes:
                send_result_to_amplify(
                    user_id, function_id, custom_routes,
                    success=False,
                    message=f"Invalid message format: missing required fields"
                )
            else:
                print(f"✗ Cannot send failure notification: insufficient data in message")
            return False

        print(f"\n{'='*80}")
        print(f"Processing new deployment request:")
        print(f"  User ID: {user_id}")
        print(f"  Function ID: {function_id}")
        print(f"  Custom Routes: {custom_routes}")
        print(f"  ECR Image: {ecr_image}")
        print(f"{'='*80}\n")

        # 0. 입력 검증
        print("[STEP 0] Validating input...")
        is_valid, validation_errors = validate_input(user_id, custom_routes)
        if not is_valid:
            error_msg = "; ".join(validation_errors)
            print(f"✗ Input validation failed: {error_msg}")
            send_result_to_amplify(
                user_id, function_id, custom_routes,
                success=False,
                message=f"Input validation failed: {error_msg}"
            )
            return False
        print("✓ Input validation passed")

        # 1. Knative Service 생성
        print("[STEP 1] Creating Knative Service...")
        if not create_knative_service(user_id, function_id, custom_routes, ecr_image):
            print("[STEP 1] Failed to create Knative Service, sending failure to Amplify...")
            send_result_to_amplify(
                user_id, function_id, custom_routes,
                success=False,
                message="Failed to create Knative Service"
            )
            return False
        print("[STEP 1] Knative Service creation completed")

        # 2. URL 생성 (Knative 기본 패턴)
        service_name = f"{user_id}-{custom_routes}".lower()
        url = f"http://{service_name}.{KNATIVE_NAMESPACE}.svc.cluster.local"
        print(f"[STEP 2] Service URL: {url}")

        # 3. Amplify에 성공 전송
        print("[STEP 3] Sending success notification to Amplify...")
        result = send_result_to_amplify(
            user_id, function_id, custom_routes,
            success=True,
            message="Deployment successful",
            url=url,
            image_digest=ecr_image
        )
        if result:
            print("[STEP 3] Success notification sent to Amplify")
        else:
            print("[STEP 3] Failed to send notification to Amplify (but deployment succeeded)")

        print("[COMPLETE] All steps finished successfully\n")
        return True

    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in message body: {e}")
        return False
    except Exception as e:
        print(f"✗ Error processing message: {e}")
        return False

def poll_sqs():
    """
    SQS 메시지 polling
    """
    print(f"Starting SQS Polling Agent...")
    print(f"Queue URL: {SQS_QUEUE_URL}")
    print(f"AWS Region: {AWS_REGION}")
    print(f"Target Namespace: {KNATIVE_NAMESPACE}")
    print(f"Poll Interval: {POLL_INTERVAL}s")
    print(f"Amplify Backend: {AMPLIFY_BACKEND_URL}")
    print(f"\nWaiting for messages...\n")

    while True:
        try:
            # SQS 메시지 수신
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # Long polling
                VisibilityTimeout=300  # 5분
            )

            messages = response.get('Messages', [])

            if not messages:
                # 메시지 없음
                continue

            for message in messages:
                receipt_handle = message['ReceiptHandle']

                # 메시지 처리
                success = process_message(message)

                # 성공하면 SQS에서 삭제
                if success:
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                    print(f"✓ Message deleted from SQS\n")
                else:
                    print(f"✗ Message processing failed, will retry later\n")

        except Exception as e:
            print(f"✗ Error in polling loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    # 환경 변수 검증
    if not SQS_QUEUE_URL:
        raise ValueError("SQS_QUEUE_URL environment variable is required")
    if not AMPLIFY_BACKEND_URL:
        raise ValueError("AMPLIFY_BACKEND_URL environment variable is required")

    # Polling 시작
    poll_sqs()