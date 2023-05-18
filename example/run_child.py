""" This script requires to be defined by user. """
import logging

import fire
import gokart
import luigi
from gokart.target import make_target

logging.basicConfig(level=logging.INFO)


def main(task_pkl_path: str) -> None:
    # Load luigi config
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")

    # Parse a serialized gokart.TaskOnKart
    task: gokart.TaskOnKart = make_target(task_pkl_path).load()

    # Run gokart.build
    gokart.build(task)


if __name__ == "__main__":
    fire.Fire(main)
