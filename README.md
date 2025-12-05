# Manifest README

<details open>
<summary>🇰🇷 한국어</summary>

## 📜 개요

이 리포지토리는 cutty-x FaaS 플랫폼의 Kubernetes 클러스터에서 실행되는 모든 애플리케이션의 매니페스트를 관리합니다. GitOps 원칙에 따라 ArgoCD를 사용하여 이 리포지토리의 변경 사항을 클러스터에 자동으로 동기화합니다.

## 📁 디렉토리 구조

-   `argocd/`: ArgoCD 애플리케이션 정의를 포함합니다.
    -   `applications/`: `app-of-apps` 패턴을 사용하여 관리되는 모든 하위 애플리케이션을 정의합니다.
-   `base/`: 각 애플리케이션의 기본 Kubernetes 매니페스트 (Kustomize 기반)를 포함합니다.
-   `ingress/`: Ingress 리소스 관련 매니페스트를 관리합니다.

## 🚀 배포된 애플리케이션

-   **ArgoCD (App-of-Apps)**: `app-of-apps.yaml`을 통해 다른 모든 ArgoCD 애플리케이션을 중앙에서 관리합니다.
-   **Knative**: 서버리스 애플리케이션을 빌드, 배포 및 관리하기 위한 Kubernetes 기반 플랫폼입니다.
    -   `knative-crds`: Knative에 필요한 Custom Resource Definitions (CRD)를 설치합니다.
    -   `knative-serving`: Knative의 핵심 컴포넌트로, 요청 기반 오토스케일링, 제로 스케일링 등을 담당합니다.
    -   `kourier`: Knative를 위한 경량 인그레스 컨트롤러입니다.
-   **Ingress**:
    -   `nginx-ingress`: 클러스터 외부에서 내부 서비스로의 HTTP 및 HTTPS 경로를 제공하는 NGINX 기반 인그레스 컨트롤러입니다.
-   **Polling Agent**: `polling-agent`는 SQS 큐를 폴링하여 새로운 함수 빌드 완료 메시지를 감지하고, 해당 정보를 기반으로 Knative 서비스 (`ksvc`)를 동적으로 생성 또는 업데이트하는 커스텀 컨트롤러입니다.
-   **ECR Token Refresher**: Kubernetes 클러스터의 노드가 프라이빗 Amazon ECR (Elastic Container Registry)에서 이미지를 가져올 수 있도록 ECR 인증 토큰을 주기적으로 갱신하는 CronJob을 배포합니다.
-   **Namespaces**: `user-functions`와 같은 프로젝트에 필요한 네임스페이스를 생성합니다.
-   **Fluent Bit**: 로그 프로세서 및 전달자입니다.
-   **gVisor**: 추가적인 보안 계층을 제공하는 애플리케이션 커널입니다.

</details>

<details>
<summary>🇯🇵 日本語</summary>

## 📜 概要

このリポジトリは、cutty-x FaaSプラットフォームのKubernetesクラスターで実行されるすべてのアプリケーションのマニフェストを管理します。GitOpsの原則に基づき、ArgoCDを使用してこのリポジトリの変更をクラスターに自動的に同期します。

## 📁 ディレクトリ構造

-   `argocd/`: ArgoCDアプリケーションの定義が含まれています。
    -   `applications/`: `app-of-apps`パターンを使用して管理されるすべてのサブアプリケーションを定義します。
-   `base/`: 各アプリケーションの基本的なKubernetesマニフェスト（Kustomizeベース）が含まれています。
-   `ingress/`: Ingressリソース関連のマニフェストを管理します。

## 🚀 デプロイされるアプリケーション

-   **ArgoCD (App-of-Apps)**: `app-of-apps.yaml`を介して、他のすべてのArgoCDアプリケーションを一元管理します。
-   **Knative**: サーバーレスアプリケーションをビルド,、デプロイ、管理するためのKubernetesベースのプラットフォームです。
    -   `knative-crds`: Knativeに必要なCustom Resource Definitions (CRD) をインストールします。
    -   `knative-serving`: Knativeのコアコンポーネントで、リクエストベースのオートスケーリング、ゼロスケーリングなどを担当します。
    -   `kourier`: Knative用の軽量なIngressコントローラーです。
-   **Ingress**:
    -   `nginx-ingress`: クラスター外部から内部サービスへのHTTPおよびHTTPSルートを提供するNGINXベースのIngressコントローラーです。
-   **Polling Agent**: `polling-agent`は、SQSキューをポーリングして新しい関数ビルド完了メッセージを検出し、その情報に基づいてKnativeサービス（`ksvc`）を動的に作成または更新するカスタムコントローラーです。
-   **ECR Token Refresher**: KubernetesクラスターのノードがプライベートのAmazon ECR（Elastic Container Registry）からイメージを取得できるように、ECR認証トークンを定期的に更新するCronJobをデプロイします。
-   **Namespaces**: `user-functions`など、プロジェクトに必要な名前空間を作成します。
-   **Fluent Bit**: ログプロセッサおよびフォワーダーです。
-   **gVisor**: 追加のセキュリティ層を提供するアプリケーションカーネルです。

</details>

<details>
<summary>🇬🇧 English</summary>

## 📜 Overview

This repository manages the manifests for all applications running on the Kubernetes cluster for the cutty-x FaaS platform. Following GitOps principles, it uses ArgoCD to automatically synchronize changes from this repository to the cluster.

## 📁 Directory Structure

-   `argocd/`: Contains the ArgoCD application definitions.
    -   `applications/`: Defines all the sub-applications managed using the `app-of-apps` pattern.
-   `base/`: Contains the base Kubernetes manifests (Kustomize-based) for each application.
-   `ingress/`: Manages manifests related to Ingress resources.

## 🚀 Deployed Applications

-   **ArgoCD (App-of-Apps)**: Centrally manages all other ArgoCD applications via `app-of-apps.yaml`.
-   **Knative**: A Kubernetes-based platform to build, deploy, and manage modern serverless workloads.
    -   `knative-crds`: Installs the Custom Resource Definitions (CRDs) required for Knative.
    -   `knative-serving`: The core component of Knative, responsible for request-based autoscaling, scale-to-zero, etc.
    -   `kourier`: A lightweight ingress controller for Knative.
-   **Ingress**:
    -   `nginx-ingress`: An NGINX-based ingress controller that provides HTTP and HTTPS routing from outside the cluster to internal services.
-   **Polling Agent**: The `polling-agent` is a custom controller that polls an SQS queue to detect new function build completion messages and dynamically creates or updates Knative services (`ksvc`) based on that information.
-   **ECR Token Refresher**: Deploys a CronJob that periodically refreshes ECR authentication tokens so that nodes in the Kubernetes cluster can pull images from a private Amazon ECR (Elastic Container Registry).
-   **Namespaces**: Creates the necessary namespaces for the project, such as `user-functions`.
-   **Fluent Bit**: A log processor and forwarder.
-   **gVisor**: An application kernel that provides an additional layer of security.

</details>
