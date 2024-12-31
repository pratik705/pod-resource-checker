# pod-resource-checker

A tool to analyze and manage resource requests and limits for Kubernetes pods.
This tool scans Kubernetes cluster, identifies pods without resource definitions, and provides recommendations based on current resource usage.
It also supports in-place updates and can be used either as a standalone executable or via a containerized version.

## Use Case

In Kubernetes, defining resource requests and limits for containers is crucial for efficient cluster management and avoiding resource contention. This tool helps:

- Identify pods missing resource requests and limits.
- Analyze current CPU and memory utilization using metrics server.
- Provide actionable recommendations for resource definitions, including `requests` and `limits`, with a user-defined buffer.
- Output resource suggestions for YAML manifests.
- Optionally update Kubernetes resources in-place(only supported in standalone mode).

### Note

The containerized version is intended for non-interactive use cases, such as:

- Identifying pods without resource definitions.
- Resource suggestions for further action.
- Generating YAML snippets for manual updates.

For interactive in-place updates, use the standalone executable.

## Usage

### 1. Standalone Executable

Download the prebuilt executable from [here](https://github.com/pratik705/pod-resource-checker/raw/refs/heads/main/downloads/pod_resources)

#### Usage

``` bash
# wget https://github.com/pratik705/pod-resource-checker/raw/refs/heads/main/downloads/pod_resources
# chmod 555 pod_resources
# ./pod_resources --namespace default --buffer-percent 20
```

### 2. Run as a Kubernetes Job

You can deploy it as a Kubernetes Job in the cluster you want to analyze. This method uses a `ServiceAccount` with appropriate `RBAC` permissions to access the required resources in the cluster.


#### Usage

- **Apply the Kubernetes Manifest**
``` bash
# export KUBECONFIG=/root/kubeconfig
# kubectl apply -f https://raw.githubusercontent.com/pratik705/pod-resource-checker/refs/heads/main/k8s_manifest.yaml
```

- **Check the Job Status**: Verify that the Job is running:
  
``` bash
# kubectl get job pod-resources-checker
# kubectl logs job/pod-resource-checker
```

- **Custom Namespace**: To scan a specific namespace, uncomment and set the `--namespace` argument in the args field of the Job YAML:
  
``` yaml
[...]
args: ["--namespace", "kube-system"]
[...]
```

- **Cleanup**: Delete the Job and associated resources when done:

``` bash
# kubectl delete -f https://raw.githubusercontent.com/pratik705/pod-resource-checker/refs/heads/main/k8s_manifest.yaml
```

---

## Output

### 1. Running as standdalone executable

- **Help page:**

``` bash
# ./pod_resources -h
usage: pod_resources [-h] [--inplace-update] [--buffer-percent BUFFER_PERCENT] [--namespace NAMESPACE]

Analyze and update Kubernetes resource requests and limits.

optional arguments:
  -h, --help            show this help message and exit
  --inplace-update      Enable in-place update of Kubernetes resources.
  --buffer-percent BUFFER_PERCENT
                        Percentage buffer to calculate resource limits (default: 20%)
  --namespace NAMESPACE
                        Namespace to scan
```

- **Scanning pods from the `test-ns` namespace:**

``` bash
# export KUBECONFIG=/root/kubeconfig

# ./pod_resources --namespace test-ns --buffer-percent 50
INFO: test-ns(Namespace)/Deployment/snapshot-controller/snapshot-controller-848dd6c6fc-zmz9v/snapshot-controller is missing resource details.
INFO: Current resource usage(as per metrics server):
╒════╤═════════════════════╤════════════════════════╕
│    │  CPU Current Usage  │  Memory Current Usage  │
╞════╪═════════════════════╪════════════════════════╡
│  0 │       641337n       │        14264Ki         │
╘════╧═════════════════════╧════════════════════════╛
INFO: Suggested resource changes:
╒════╤═══════════════════════════╤══════════════════════════════╤═════════════════════════╤════════════════════════════╕
│    │  CPU Request(suggestion)  │  Memory Request(suggestion)  │  CPU Limit(suggestion)  │  Memory Limit(suggestion)  │
╞════╪═══════════════════════════╪══════════════════════════════╪═════════════════════════╪════════════════════════════╡
│  0 │          641337n          │           14264Ki            │         962005n         │          21396Ki           │
╘════╧═══════════════════════════╧══════════════════════════════╧═════════════════════════╧════════════════════════════╛
----------------------------
Suggested resource section for the manifest in yaml format:
[...]
spec:
    containers:
    - name: snapshot-controller
      resources:
          limits:
              cpu: 962005n
              memory: 21396Ki
          requests:
              cpu: 641337n
              memory: 14264Ki
[...]
----------------------------
```

- **Scanning and inplace-update the pods from `test-ns` namespace:**

``` bash
# export KUBECONFIG=/root/kubeconfig

# ./pod_resources --namespace test-ns --buffer-percent 50 --inplace-update
INFO: test-ns(Namespace)/StatefulSet/argocd-application-controller/argocd-application-controller-0/application-controller is missing resource details.
INFO: Current resource usage(as per metrics server):
╒════╤═════════════════════╤════════════════════════╕
│    │  CPU Current Usage  │  Memory Current Usage  │
╞════╪═════════════════════╪════════════════════════╡
│  0 │      40340605n      │        354128Ki        │
╘════╧═════════════════════╧════════════════════════╛
INFO: Suggested resource changes:
╒════╤═══════════════════════════╤══════════════════════════════╤═════════════════════════╤════════════════════════════╕
│    │  CPU Request(suggestion)  │  Memory Request(suggestion)  │  CPU Limit(suggestion)  │  Memory Limit(suggestion)  │
╞════╪═══════════════════════════╪══════════════════════════════╪═════════════════════════╪════════════════════════════╡
│  0 │         40340605n         │           354128Ki           │        60510907n        │          531192Ki          │
╘════╧═══════════════════════════╧══════════════════════════════╧═════════════════════════╧════════════════════════════╛
----------------------------
Suggested resource section for the manifest in yaml format:
[...]
spec:
    containers:
    - name: application-controller
      resources:
          limits:
              cpu: 60510907n
              memory: 531192Ki
          requests:
              cpu: 40340605n
              memory: 354128Ki
[...]
----------------------------

Do you want to apply the changes to the top-level parent resource? (yes/no): yes
Is this resource managed by GitOps/version control? (yes/no): no
INFO: Updated StatefulSet argocd-application-controller in namespace test-ns.
INFO: If the resources are managed by helm then make sure that the values.yaml is updated with the changes.
```

- **Validating the change:**

``` bash
# kubectl get pod argocd-application-controller-0 -n test-ns
NAME                              READY   STATUS    RESTARTS   AGE
argocd-application-controller-0   1/1     Running   0          37s

# kubectl get sts argocd-application-controller -n test-ns -o yaml |less
[...]
      containers:
        name: application-controller      
        resources:
          limits:
            cpu: 61m
            memory: 531192Ki
          requests:
            cpu: 41m
            memory: 354128Ki
[...]
```

---

### 2. Running as Kubernetes job

``` shell
# kubectl logs job/pod-resources-checker
[...]
INFO: wordpress(Namespace)/StatefulSet/wordpress-mariadb/wordpress-mariadb-0/mariadb is missing resource details.
INFO: Current resource usage(as per metrics server):
╒════╤═════════════════════╤════════════════════════╕
│    │  CPU Current Usage  │  Memory Current Usage  │
╞════╪═════════════════════╪════════════════════════╡
│  0 │      4942470n       │        392392Ki        │
╘════╧═════════════════════╧════════════════════════╛
INFO: Suggested resource changes:
╒════╤═══════════════════════════╤══════════════════════════════╤═════════════════════════╤════════════════════════════╕
│    │  CPU Request(suggestion)  │  Memory Request(suggestion)  │  CPU Limit(suggestion)  │  Memory Limit(suggestion)  │
╞════╪═══════════════════════════╪══════════════════════════════╪═════════════════════════╪════════════════════════════╡
│  0 │         4942470n          │           392392Ki           │        5930964n         │          470870Ki          │
╘════╧═══════════════════════════╧══════════════════════════════╧═════════════════════════╧════════════════════════════╛
----------------------------
Suggested resource section for the manifest in yaml format:
[...]
spec:
    containers:
    - name: mariadb
      resources:
          limits:
              cpu: 5930964n
              memory: 470870Ki
          requests:
              cpu: 4942470n
              memory: 392392Ki
[...]
----------------------------
```

---

## **Disclaimer**

This tool is intended for use in test or development environments first. Validate its behavior before using it in production. Use the `--inplace-update` flag cautiously, as it directly modifies resource configurations.
