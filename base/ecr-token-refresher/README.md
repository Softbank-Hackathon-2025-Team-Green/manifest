# ECR Token Refresher

ECR 토큰을 자동으로 갱신하는 CronJob입니다.

## 기능

- **자동 갱신**: 10시간마다 ECR 토큰 자동 갱신
- **초기 실행**: 배포 직후 즉시 토큰 생성 (init-job)
- **ServiceAccount 연동**: default ServiceAccount에 자동으로 imagePullSecrets 설정

## 사전 요구사항

AWS Credentials Secret이 필요합니다:

```bash
kubectl create secret generic aws-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=<your-key> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<your-secret> \
  -n user-functions
```

## 설치

```bash
# Kustomize로 설치
kubectl apply -k base/ecr-token-refresher/

# 또는 ArgoCD Application으로 관리
kubectl apply -f argocd/applications/ecr-token-refresher.yaml
```

## 수동 실행

CronJob 스케줄을 기다리지 않고 즉시 실행:

```bash
# 기존 테스트 Job 삭제
kubectl delete job ecr-test-refresh -n user-functions --ignore-not-found

# 새 Job 생성 (CronJob에서)
kubectl create job -n user-functions \
  --from=cronjob/ecr-token-refresh \
  ecr-test-refresh

# 로그 확인
kubectl logs -n user-functions -l job-name=ecr-test-refresh -f
```

## 확인

```bash
# CronJob 상태
kubectl get cronjob -n user-functions

# Job 실행 이력
kubectl get jobs -n user-functions -l app=ecr-token-refresher

# Secret 확인
kubectl get secret ecr-secret -n user-functions

# ServiceAccount에 imagePullSecrets 설정 확인
kubectl get sa default -n user-functions -o yaml | grep imagePullSecrets -A 2
```

## 환경별 설정

### Registry 변경

다른 ECR 레포지토리를 사용하려면 `cronjob.yaml`과 `init-job.yaml`의 환경 변수를 수정:

```yaml
env:
  - name: ECR_REGISTRY
    value: "YOUR_ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com"
  - name: ECR_REPO
    value: "your-repo-name"
```

### 스케줄 변경

토큰 갱신 주기를 변경하려면 `cronjob.yaml`의 schedule 수정:

```yaml
spec:
  schedule: "0 */8 * * *"  # 8시간마다
```

## 트러블슈팅

### Job이 실패하는 경우

```bash
# Job 로그 확인
kubectl logs -n user-functions -l app=ecr-token-refresher --tail=50

# Job 상세 정보
kubectl describe job -n user-functions -l app=ecr-token-refresher

# AWS Credentials 확인
kubectl get secret aws-credentials -n user-functions -o yaml
```

### Secret이 생성되지 않는 경우

```bash
# RBAC 권한 확인
kubectl auth can-i create secrets -n user-functions \
  --as=system:serviceaccount:user-functions:ecr-refresher

# ServiceAccount 확인
kubectl get sa ecr-refresher -n user-functions
```

### ECR 토큰 수동 갱신

```bash
# 수동으로 토큰 생성
TOKEN=$(aws ecr get-login-password --region ap-northeast-2)

kubectl delete secret ecr-secret -n user-functions --ignore-not-found

kubectl create secret docker-registry ecr-secret \
  --docker-server=900253478827.dkr.ecr.ap-northeast-2.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$TOKEN \
  -n user-functions

kubectl patch serviceaccount default \
  -p '{"imagePullSecrets": [{"name": "ecr-secret"}]}' \
  -n user-functions
```
