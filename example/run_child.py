""" This script requires to be defined by user. """
import logging

import fire
import gokart
import luigi
# Import task definition
import tasks

logging.basicConfig(level=logging.INFO)


def main(serialized_task: str):
    # Load luigi config
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")

    # Parse a serialized gokart.TaskOnKart
    task: gokart.TaskOnKart = gokart.TaskInstanceParameter().parse(serialized_task)

    # Run gokart.build
    gokart.build(task)


if __name__ == "__main__":
    fire.Fire(main)
