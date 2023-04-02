import unittest

import gokart
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
                    namespace=None,
                    image_name=None,
                    container_name=None,
                    job_prefix=None,
                    path_child_script=__file__,
                    env_to_inherit=None,
                    service_account_name=None,
                )
                master._create_task_queue(case)


if __name__ == '__main__':
    unittest.main()
