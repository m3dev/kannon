import unittest

import gokart
from kubernetes import client

from kannon import Kannon


class TestStringMethods(unittest.TestCase):

    def test_create_task_queue(self):

        class Example(gokart.TaskOnKart):
            pass

        class Dict(gokart.TaskOnKart):

            def requires(self):
                return dict(example=Example())

        class List(gokart.TaskOnKart):

            def requires(self):
                return [Example()]

        class ListInDict(gokart.TaskOnKart):

            def requires(self):
                return dict(example=[Example()])

        class Single(gokart.TaskOnKart):

            def requires(self):
                return Example()

        cases = [Dict(), List(), ListInDict(), Single()]
        for case in cases:
            with self.subTest(case=case):
                master = Kannon(
                    api_instance=None,
                    template_job=client.V1Job(metadata=client.V1ObjectMeta()),
                    job_prefix=None,
                    path_child_script=__file__,  # just pass any existing file as dummy
                    env_to_inherit=None,
                )
                master._create_task_queue(case)


if __name__ == '__main__':
    unittest.main()
