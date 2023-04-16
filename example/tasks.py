from time import sleep
from typing import Dict

import gokart
import luigi

import kannon


class TaskA(gokart.TaskOnKart):
    param = luigi.Parameter()

    def run(self) -> None:
        sleep(5)
        self.dump("A")


class TaskB(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent": self.parent}

    def run(self) -> None:
        sleep(5)
        self.dump("B")


class TaskC(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent": self.parent}

    def run(self) -> None:
        sleep(30)
        self.dump("C")


class TaskD(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent": self.parent}

    def run(self) -> None:
        sleep(30)
        self.dump("D")


class TaskE(kannon.TaskOnBullet):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent": self.parent}

    def run(self) -> None:
        sleep(30)
        self.dump("E")


class TaskF(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent_0 = gokart.TaskInstanceParameter()
    parent_1 = gokart.TaskInstanceParameter()
    parent_2 = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent_0": self.parent_0, "parent_1": self.parent_1, "parent_2": self.parent_2}

    def run(self) -> None:
        sleep(5)
        self.dump("F")


class TaskG(gokart.TaskOnKart):
    param = luigi.Parameter()
    parent = gokart.TaskInstanceParameter()

    def requires(self) -> Dict[str, gokart.TaskInstanceParameter]:
        return {"parent": self.parent}

    def run(self) -> None:
        sleep(5)
        self.dump("G")
