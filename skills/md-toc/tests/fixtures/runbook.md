# EKS Upgrade Runbook: 1.29 → 1.31

This runbook covers upgrading the production EKS cluster from Kubernetes 1.29 to 1.31 in two hops. It was written after the staging upgrade on 3 November 2026, which took 2 hours 40 minutes and surfaced three issues worth planning around. Read [Known issues & workarounds](#known-issues--workarounds) before starting, and keep the [Rollback plan](#rollback-plan) open in another tab.

## Background

The cluster runs 42 nodes across three managed node groups. EKS standard support for 1.29 ends on 23 March 2027, after which extended support costs $0.60 per cluster-hour instead of $0.10. Upgrading two minor versions now avoids roughly $3,600 a month in extended-support charges and unblocks the Karpenter 1.x migration, which needs 1.30 or later.

Kubernetes control planes can only move one minor version at a time, so the upgrade is two separate hops: 1.29 to 1.30, then 1.30 to 1.31. Each hop upgrades the control plane first, then the add-ons, then the node groups.

## Prerequisites

### Access & permissions

You need the `eks-admin` role in the production account and a working `kubectl` context. Confirm with `aws sts get-caller-identity` and `kubectl get nodes`. The change window must be approved in the change calendar at least 48 hours ahead.

### Tooling: `kubectl`, `eksctl` & `pluto`

Install `kubectl` 1.31, `eksctl` 0.190 or later, and `pluto` for deprecated API detection. Run `pluto detect-helm -o wide` against the cluster and fix every result marked *removed* before the first hop; see [Deprecated APIs](#deprecated-apis).

### Backups

Take a Velero backup of all namespaces and confirm it completes. Export the Terraform state for the cluster module. Snapshot the EBS volumes behind the two stateful sets (Postgres and Redis).

## Upgrade steps

### Step 1: Control plane 1.29 → 1.30

Bump `cluster_version` to `1.30` in Terraform and apply. The control-plane upgrade takes 8 to 12 minutes and does not interrupt running workloads. Watch the cluster status in the console until it reads *Active*.

### Step 2: Add-ons (VPC CNI, CoreDNS, kube-proxy)

Upgrade the managed add-ons to the versions compatible with 1.30. Upgrade VPC CNI first: an old CNI on new nodes is the most common cause of pods stuck in `ContainerCreating`. CoreDNS and kube-proxy follow.

### Step 3: Node groups

Roll each node group with a max-unavailable of 10 percent. The rollout respects PodDisruptionBudgets, so it will stall if a PDB allows zero disruptions; see [PDBs blocking drain](#pdbs-blocking-drain).

### Step 4: Repeat for 1.30 → 1.31

Repeat steps 1 to 3 with `cluster_version = "1.31"`. Leave at least 30 minutes between hops to confirm metrics are stable.

## Known issues & workarounds

### Deprecated APIs

Staging had two Helm releases still using `flowcontrol.apiserver.k8s.io/v1beta3`, which is removed in 1.32 but already warned on in 1.31. Upgrade those charts before the second hop so the warnings don't hide real problems.

### PDBs blocking drain

The `payments-api` PodDisruptionBudget sets `minAvailable: 100%`, so drains never finish. Temporarily patch it to `maxUnavailable: 1` for the window, and restore it afterwards.

### CoreDNS 🐢 slow to settle

After the CoreDNS upgrade, DNS latency rose for about four minutes on staging. Scale CoreDNS to six replicas before the upgrade and back to three afterwards.

## Validation

After each hop, check node versions with `kubectl get nodes`, confirm every deployment is fully available, run the smoke-test suite, and compare p95 latency in Grafana against the hour before the window. Any regression above 15 percent means stopping and following the [Rollback plan](#rollback-plan).

## Rollback plan

The control plane cannot be downgraded. Rollback therefore means keeping workloads on the old node group: keep the previous node group at full size until validation passes, and cordon the new one if needed. For data problems, restore from the Velero backup taken in [Backups](#backups).

## FAQ

### How long does the whole upgrade take?

About five hours for both hops, including validation, based on staging.

### Can we skip 1.30?

No. EKS only upgrades one minor version at a time.

## Contacts

Platform on-call owns the window. Escalate to the AWS TAM for control-plane issues that last more than 30 minutes.
