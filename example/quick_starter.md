# Quick Starter
This is a easy and self-contained tutorial of `kannon`.

## Requirements
### Install Docker
Install docker from [Get Docker](https://docs.docker.com/get-docker/).

### Install minikube
Install minikube following the instruction on the [minikube start](https://minikube.sigs.k8s.io/docs/start/) document. Make sure the whole setup completed successfully.



## Steps
### 1. Start minikube
Make sure the docker daemon is running.
```bash
$ minikube start
```

### 2. Build docker image
Enable to push a local docker image to the docker daemon within the minikube cluster.
The detail is given [here](https://minikube.sigs.k8s.io/docs/handbook/pushing/#1-pushing-directly-to-the-in-cluster-docker-daemon-docker-env).
```bash
$ eval $(minikube docker-env)
```

Build a docker image from `example/Dockerfile`.
```bash
$ cd ./example
$ docker build -t kannon_quick_starter .
```

Now, the docker image is available within the cluster.

### 3. Create the required Kubernetes resources
Create a new namespace `kannon-quick-starter`.
```bash
$ minikube kubectl -- apply -f k8s/ns.yaml
namespace/kannon-quick-starter created
```

Create a new service account, role, and role-biding.
```bash
$ minikube kubectl -- apply -f k8s/sa.yaml
serviceaccount/job-manager created
role.rbac.authorization.k8s.io/job-manager-role created
rolebinding.rbac.authorization.k8s.io/job-manager-rolebinding created
```

Create a new persistent volume and persistent volume claim, which is used as a common cache for multiple k8s jobs.
```bash
$ minikube kubectl -- apply -f k8s/pv.yaml
persistentvolume/kannon-cache created
persistentvolumeclaim/kannon-cache-claim created
```


### 4. Check task definition
gokart tasks to be run are defined in `example/tasks.py`.

In this quick starter, the following tasks will be run.
Each block represents a single task, `TaskName (duration)`

<div align="center">

![](./image/quick_starter_task.jpeg)

</div>

In `tasks.py`, `TaskC`, `TaskD`, and `TaskD` inherits `kannon.TaskOnBullet` instead of `gokart.TaskOnKart`, so Task C0-C2, D0-D2, and E0-E2 are run on different jobs in parallel.

```python
# example/tasks.py
class TaskC(kannon.TaskOnBullet):
    ...

class TaskD(kannon.TaskOnBullet):
    ...

class TaskE(kannon.TaskOnBullet):
    ...
```

Since Task C, D, and E are tasks that will take longer time than other tasks and they can be run in parallel, `kannon` will be very effective! Let's check it.


### 5. Run master job
Run the master job!
```bash
$ minikube kubectl -- apply -f k8s/master-job.yaml
job.batch/master-job-quick-starter created
```

Let's check running jobs. You can see 3 child tasks are running on multiple jobs in parallel.
```bash
$ minikube kubectl -- get jobs -n kannon-quick-starter
NAME                                     COMPLETIONS   DURATION   AGE
master-job-quick-starter                 0/1           7m23s      7m23s
# task c0, c1, c2 are done in parallel.
quick-starter-taskc-014-20230413142312   1/1           3m5s       6m52s
quick-starter-taskc-036-20230413142309   1/1           3m5s       6m55s
quick-starter-taskc-191-20230413142306   1/1           3m6s       6m58s
# then, task d0, d1, d2 are done in parallel.
quick-starter-taskd-079-20230413142613   1/1           3m7s       3m51s
quick-starter-taskd-118-20230413142615   1/1           3m6s       3m49s
quick-starter-taskd-143-20230413142617   1/1           3m7s       3m47s
# finally, task e0, e1, e2 are running in parallel now.
quick-starter-taske-071-20230413142923   0/1           41s        41s
quick-starter-taske-091-20230413142924   0/1           40s        40s
quick-starter-taske-146-20230413142922   0/1           42s        42s
```

### 6. Check the result

```bash
$ minikube kubectl --  get jobs -n kannon-quick-starter
NAME                                     COMPLETIONS   DURATION   AGE
master-job-quick-starter                 1/1           11m        14m
quick-starter-taskc-014-20230413142312   1/1           3m5s       14m
quick-starter-taskc-036-20230413142309   1/1           3m5s       14m
quick-starter-taskc-191-20230413142306   1/1           3m6s       14m
quick-starter-taskd-079-20230413142613   1/1           3m7s       11m
quick-starter-taskd-118-20230413142615   1/1           3m6s       11m
quick-starter-taskd-143-20230413142617   1/1           3m7s       11m
quick-starter-taske-071-20230413142923   1/1           4m5s       8m12s
quick-starter-taske-091-20230413142924   1/1           4m6s       8m11s
quick-starter-taske-146-20230413142922   1/1           4m5s       8m13s
```

All jobs are completed successfully!
Duration for the master job to be completed is `11m`.
Compared to the case without `kannon`, it is almost **3x** faster!

|using kannon? | duration |
|---|---|
|yes | **11 minutes**|
|no | 31 minutes|


### (Optional) Delete cache to retry this quick starter.
```bash
$ minikube kubectl -- apply -f k8s/temp-pod.yaml
pod/temp-pod created

$ minikube kubectl -- exec -it temp-pod -n kannon-quick-starter -- /bin/sh
```

Within `temp-pod`, execute the following commands.
```
/ #
/ # ls cache/
log    tasks
/ # rm -rf cache/*
```
Now, all caches save on the persistent volume `kannon-cache` are cleared.
