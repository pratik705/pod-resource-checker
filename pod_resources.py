import argparse
from kubernetes import config, client
from tabulate import tabulate

config.load_kube_config()
parser = argparse.ArgumentParser(
    description="Analyze and update Kubernetes resource requests and limits."
)
parser.add_argument(
    "--inplace-update",
    action="store_true",
    help="Enable in-place update of Kubernetes resources."
)
parser.add_argument(
    "--buffer-percent",
    type=int,
    default=20,
    help="Percentage buffer to calculate resource limits (default: 20%%)"
)
parser.add_argument(
    "--namespace",
    type=str,
    help="Namespace to scan"
)

args = parser.parse_args()
v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()
BUFFER_PERCENT = args.buffer_percent
DEFAULT_CPU_REQUEST = "10m"
DEFAULT_MEMORY_REQUEST = "32Mi"

if args.buffer_percent < 0 or args.buffer_percent > 100:
    parser.error("--buffer-percent must be between 0 and 100.")


def fetch_resource_usage(namespace, pod_name, container_name):
    '''
    Function to fetch current resource usage
    '''
    try:
        metrics_api = client.CustomObjectsApi()
        metrics = metrics_api.get_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
            name=pod_name
        )
        for container in metrics["containers"]:
            if container["name"] == container_name:
                usage = container["usage"]
                return usage["cpu"], usage["memory"]
    except Exception:
        return None, None


def generate_resource_manifest(container_name, cpu_request, memory_request, cpu_limit, memory_limit):
    """
    Generate a YAML snippet for resource requests and limits.
    """
    yaml_snippet = f"""
[...]
spec:
    containers:
    - name: {container_name}
      resources:
          limits:
              cpu: {cpu_limit}
              memory: {memory_limit}
          requests:
              cpu: {cpu_request if len(cpu_request[:-1]) > 0 else DEFAULT_CPU_REQUEST}
              memory: {memory_request}
[...]
    """
    return yaml_snippet.strip()


def find_top_level_resource(namespace, owner_kind, owner_name):
    '''
    Function to determine top-level parent resource
    '''
    if owner_kind == "ReplicaSet":
        replicaset = apps_v1.read_namespaced_replica_set(
            name=owner_name, namespace=namespace
        )
        if replicaset.metadata.owner_references:
            owner = replicaset.metadata.owner_references[0]
            return owner.kind, owner.name
        else:
            return "ReplicaSet", owner_name
    else:
        return owner_kind, owner_name


def update_resource(parent_kind, namespace, parent_name, container_name, cpu_request, memory_request, cpu_limit, memory_limit):
    '''
    Function to update resources
    '''
    if parent_kind == "Deployment":
        deployment = apps_v1.read_namespaced_deployment(
            name=parent_name, namespace=namespace
        )
        for container in deployment.spec.template.spec.containers:
            if container.name == container_name:
                container.resources.requests = {
                    "cpu": cpu_request, "memory": memory_request
                }
                container.resources.limits = {
                    "cpu": cpu_limit, "memory": memory_limit
                }
        apps_v1.patch_namespaced_deployment(
            name=parent_name, namespace=namespace, body=deployment
        )
        print(f"INFO: Updated Deployment {parent_name} in namespace {namespace}.")
    elif parent_kind == "StatefulSet":
        statefulset = apps_v1.read_namespaced_stateful_set(
            name=parent_name, namespace=namespace
        )
        for container in statefulset.spec.template.spec.containers:
            if container.name == container_name:
                container.resources.requests = {
                    "cpu": cpu_request, "memory": memory_request
                }
                container.resources.limits = {
                    "cpu": cpu_limit, "memory": memory_limit
                }
        apps_v1.patch_namespaced_stateful_set(
            name=parent_name, namespace=namespace, body=statefulset
        )
        print(f"INFO: Updated StatefulSet {parent_name} in namespace {namespace}.")
    elif parent_kind == "DaemonSet":
        daemonset = apps_v1.read_namespaced_daemon_set(
            name=parent_name, namespace=namespace
        )
        for container in daemonset.spec.template.spec.containers:
            if container.name == container_name:
                container.resources.requests = {
                    "cpu": cpu_request, "memory": memory_request
                }
                container.resources.limits = {
                    "cpu": cpu_limit, "memory": memory_limit
                }
        apps_v1.patch_namespaced_daemon_set(
            name=parent_name, namespace=namespace, body=daemonset
        )
        print(f"INFO: Updated DaemonSet {parent_name} in namespace {namespace}.")
    else:
        print(f"INFO: Unsupported top-level resource {parent_kind}. Please update manually.")


def inplace_update(parent_kind, namespace, parent_name, container_name, cpu_request, memory_request, cpu_limit, memory_limit):
    '''
    Perform inplace update
    '''
    user_input = input(
        "Do you want to apply the changes to the top-level parent resource? (yes/no): "
    ).strip().lower()
    if user_input == "yes":
        gitops_managed = input(
            "Is this resource managed by GitOps/version control? (yes/no): "
        ).strip().lower()
        if gitops_managed == "yes":
            print(
                f"INFO: Please update the manifest for {namespace}(Namespace)/{parent_kind}/{parent_name} in your GitOps repository or version control system."
            )
        else:
            update_resource(
                parent_kind, namespace, parent_name, container_name,
                cpu_request, memory_request, cpu_limit, memory_limit
            )
            print(
                "INFO: If the resources are managed by helm then make sure that the values.yaml is updated with the changes.\n"
            )
    else:
        print("INFO: No changes were made.")


def print_data(cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit, namespace, pod_name, container_name, resource_manifest,parent_kind=None, parent_name=None):
    '''
    Print the output
    '''
    tabular_data_current = [[cpu_usage, memory_usage]]
    table_current = tabulate(
        tabular_data_current,
        headers=["CPU Current Usage", "Memory Current Usage"],
        tablefmt="fancy_grid",
        stralign="center",
        showindex=True
    )
    tabular_data_suggestion = [
            [((cpu_request) if len(cpu_usage[:-1]) > 0 else DEFAULT_CPU_REQUEST), memory_request, cpu_limit, memory_limit]
    ]
    table_suggestion = tabulate(
        tabular_data_suggestion,
        headers=[
            "CPU Request(suggestion)", "Memory Request(suggestion)",
            "CPU Limit(suggestion)", "Memory Limit(suggestion)"
        ],
        tablefmt="fancy_grid",
        stralign="center",
        showindex=True
    )
    print(
        f"INFO: {namespace}(Namespace)/{parent_kind}/{parent_name}/{pod_name}/{container_name} is missing resource details.\n"
        f"INFO: Current resource usage(as per metrics server): \n{table_current}\n"
        f"INFO: Suggested resource changes: \n{table_suggestion}\n"
        f"----------------------------\n"
        f"Suggested resource section for the manifest in yaml format:\n{resource_manifest}\n"
        f"----------------------------\n"
    )


def query_pods(pods):
    '''
    Query Pods
    '''
    for pod in pods.items:
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name
        for container in pod.spec.containers:
            resources = container.resources
            if not resources.requests or not resources.limits:
                cpu_usage, memory_usage = fetch_resource_usage(
                    namespace, pod_name, container.name
                )

                if not cpu_usage or not memory_usage:
                    print(
                        f"WARNING: Metrics unavailable for {namespace}/{pod_name}. Skipping."
                    )
                    continue

                if cpu_usage and memory_usage:
                    cpu_request_unit = cpu_usage[-1]
                    memory_request_unit = memory_usage[-2:]
                    cpu_request = cpu_usage
                    memory_request = memory_usage
                    cpu_limit = f'{int((int(cpu_usage[:-1]) if len(cpu_usage) > 1 else int(DEFAULT_CPU_REQUEST[:-1])) * (1 + BUFFER_PERCENT / 100))}{cpu_request_unit if len(cpu_usage) > 1 else "m"}'
                    memory_limit = f"{int((int(memory_usage[:-2] if len(memory_usage) > 1 else int(DEFAULT_MEMORY_REQUEST[:-2]))) * (1 + BUFFER_PERCENT / 100))}{memory_request_unit}"

                    owner_references = pod.metadata.owner_references
                    if owner_references:
                        owner = owner_references[0]
                        parent_kind, parent_name = find_top_level_resource(
                            namespace, owner.kind, owner.name
                        )
                        resource_manifest = generate_resource_manifest(
                            container.name, cpu_request, memory_request, cpu_limit, memory_limit
                        )
                        print_data(cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit, namespace, pod_name, container.name, resource_manifest, parent_kind, parent_name)

                    else:
                        resource_manifest = generate_resource_manifest(
                            container.name, cpu_request, memory_request, cpu_limit, memory_limit)
                        print_data(cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit, namespace, pod_name, container.name, resource_manifest)

                    if args.inplace_update:
                        inplace_update(
                            parent_kind, namespace, parent_name, container.name,
                            cpu_request, memory_request, cpu_limit, memory_limit
                        )



def pods_all_namespaces():
    '''
    Operation on the pods from all the namespaces in the cluster
    '''
    pods = v1.list_pod_for_all_namespaces()
    query_pods(pods)


def pods_namespaces(namespace):
    '''
    Operation on the pods from specific namespace in the cluster
    '''
    pods = v1.list_namespaced_pod(namespace=namespace)
    query_pods(pods)


def main():
    '''
    Main function
    '''
    if args.namespace:
        namespace = args.namespace
        pods_namespaces(namespace)
    else:
        pods_all_namespaces()

main()
