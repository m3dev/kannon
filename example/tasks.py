from time import sleep

import gokart
import luigi

import kannon


class TaskA(gokart.TaskOnKart):
    param = luigi.Parameter()

    def run(self):
        sleep(10)
        self.dump("A")


class TaskB(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent": self.parent}

    def run(self):
        sleep(10)
        self.dump("B")


class TaskC(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent": self.parent}

    def run(self):
        sleep(60 * 3)
        self.dump("C")


class TaskD(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent": self.parent}

    def run(self):
        sleep(60 * 3)
        self.dump("D")


class TaskE(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent": self.parent}

    def run(self):
        sleep(60 * 4)
        self.dump("E")


class TaskF(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent_0 = gokart.TaskInstanceParameter()
    parent_1 = gokart.TaskInstanceParameter()
    parent_2 = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent_0": self.parent_0, "parent_1": self.parent_1, "parent_2": self.parent_2}

    def run(self):
        sleep(10)
        self.dump("F")


class TaskG(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self):
        return {"parent": self.parent}

    def run(self):
        sleep(10)
        self.dump("G")
