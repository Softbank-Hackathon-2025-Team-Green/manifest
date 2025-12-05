# Polling Agent 빌드 및 배포 가이드

## 1. Docker 이미지 빌드

### 1.1 ECR 레포지토리 생성 (처음 한 번만)
```bash
aws ecr create-repository \
  --repository-name polling-agent \
  --region ap-northeast-2
```

### 1.2 ECR 로그인
```bash
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  900253478827.dkr.ecr.ap-northeast-2.amazonaws.com
```

### 1.3 Docker 이미지 빌드
```bash
cd /root/project/manifest/polling-agent

docker build -t polling-agent:latest .
```

### 1.4 이미지 태그 및 푸시
```bash
docker tag polling-agent:latest \
  900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/polling-agent:latest

docker push 900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/polling-agent:latest
```

## 2. ConfigMap 업데이트

배포하기 전에 실제 값으로 ConfigMap을 업데이트하세요:

```bash
# configmap.yaml 편집
vi configmap.yaml
```

다음 값들을 실제 값으로 변경:
- `SQS_QUEUE_URL`: 실제 SQS Queue URL
- `AMPLIFY_BACKEND_URL`: 실제 Amplify Backend URL (https://your-domain.com)

## 3. Kubernetes 배포

### 3.1 ArgoCD Application 생성

ArgoCD를 사용하는 경우:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: polling-agent
  namespace: argocd
  labels:
    app.kubernetes.io/name: polling-agent
    app.kubernetes.io/part-of: knative-faas-platform
  annotations:
    argocd.argoproj.io/sync-wave: "2"
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: git@github.com:Softbank-Hackathon-2025-Team-Green/manifest.git
    targetRevision: HEAD
    path: base/polling-agent
  destination:
    server: https://kubernetes.default.svc
    namespace: user-functions
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

### 3.2 수동 배포 (ArgoCD 없이)

```bash
cd /root/project/manifest/base/polling-agent

# Kustomize로 배포
kubectl apply -k .
```

## 4. 배포 확인

```bash
# Pod 상태 확인
kubectl get pods -n user-functions -l app=polling-agent

# 로그 확인
kubectl logs -n user-functions -l app=polling-agent -f

# Knative Service 권한 확인
kubectl auth can-i create services.serving.knative.dev \
  --as=system:serviceaccount:user-functions:polling-agent \
  -n user-functions
```

## 5. 테스트

### 5.1 SQS 메시지 전송 테스트

```bash
aws sqs send-message \
  --queue-url https://sqs.ap-northeast-2.amazonaws.com/YOUR_ACCOUNT_ID/YOUR_QUEUE_NAME \
  --message-body '{
    "userId": "testuser123",
    "functionId": "func456",
    "customRoutes": "hello",
    "ecrImage": "900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/buildpack-test:latest"
  }' \
  --region ap-northeast-2
```

### 5.2 생성된 Knative Service 확인

```bash
# Knative Service 확인
kubectl get ksvc -n user-functions

# 특정 서비스 상세 확인
kubectl get ksvc testuser123-hello -n user-functions -o yaml
```

### 5.3 Amplify 백엔드 콜백 확인

Amplify 백엔드에서 다음 엔드포인트로 요청이 왔는지 확인:
- 성공: `POST /api/deploy/success`
- 실패: `POST /api/deploy/failed`

## 6. 트러블슈팅

### Pod가 ImagePullBackOff 상태인 경우

```bash
# ECR Secret 확인
kubectl get secret ecr-secret -n user-functions

# ECR Secret이 없으면 ECR Token Refresher가 실행되었는지 확인
kubectl get pods -n user-functions -l app=ecr-token-refresher
```

### Knative Service 생성 권한 오류

```bash
# RBAC 확인
kubectl get role,rolebinding -n user-functions -l app=polling-agent

# ServiceAccount 확인
kubectl get sa polling-agent -n user-functions
```

### SQS 접근 권한 오류

EC2 인스턴스에 적절한 IAM Role이 연결되어 있는지 확인:
- EC2 Instance → IAM Role → SQS 접근 정책 필요

```bash
# Node의 IAM Role 확인
aws ec2 describe-instances \
  --instance-ids <instance-id> \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'
```

### Amplify 백엔드 연결 실패

```bash
# Pod 로그에서 에러 확인
kubectl logs -n user-functions -l app=polling-agent --tail=100

# ConfigMap 값 확인
kubectl get configmap polling-agent-config -n user-functions -o yaml
```

## 7. 업데이트

### 코드 변경 후 재배포

```bash
# 1. 이미지 재빌드
docker build -t polling-agent:latest .

# 2. 새 태그로 푸시 (버전 태그 사용 권장)
docker tag polling-agent:latest \
  900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/polling-agent:v1.0.1

docker push 900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/polling-agent:v1.0.1

# 3. Deployment 이미지 업데이트
kubectl set image deployment/polling-agent \
  polling-agent=900253478827.dkr.ecr.ap-northeast-2.amazonaws.com/polling-agent:v1.0.1 \
  -n user-functions

# 또는 ArgoCD 사용 시 자동 sync
kubectl patch application polling-agent -n argocd --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

## 8. 제거

```bash
# ArgoCD Application 삭제
kubectl delete application polling-agent -n argocd

# 또는 수동 삭제
kubectl delete -k /root/project/manifest/base/polling-agent
```
