""" This script requires to be defined by user. """
import logging
from typing import List

import os
import fire
import gokart
import luigi
from gokart.target import make_target

logging.basicConfig(level=logging.INFO)


def main(task_pkl_path: str, remote_config_paths: List[str]) -> None:
    # Load luigi config
    luigi.configuration.LuigiConfigParser.add_config_path("./conf/base.ini")
    for remote_config_path in remote_config_paths:
        conf = make_target(remote_config_path).load()
        # copy to pod local
        local_path = os.path.join("./conf", os.path.basename(remote_config_path))
        make_target(local_path).dump(conf)
        luigi.configuration.LuigiConfigParser.add_config_path(local_path)

    # Parse a serialized gokart.TaskOnKart
    task: gokart.TaskOnKart = make_target(task_pkl_path).load()

    # Run gokart.build
    gokart.build(task)


if __name__ == "__main__":
    fire.Fire(main)
