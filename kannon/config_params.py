from typing import Any, Dict, Optional, Type

import gokart
import luigi


class inherits_config_params:

    def __init__(self, config_class: luigi.Config, parameter_alias: Optional[Dict[str, str]] = None):
        """
        Decorates task to inherit parameter value of `config_class`.

        * config_class: Inherit parameter value of this task to decorated task. Only parameter values exist in both tasks are inherited.
        * parameter_alias: Dictionary to map paramter names between config_class task and decorated task.
                           key: config_class's parameter name. value: decorated task's parameter name.
        """

        self._config_class: luigi.Config = config_class
        self._parameter_alias: Dict[str, str] = parameter_alias if parameter_alias is not None else {}

    def __call__(self, task_class: Type[gokart.TaskOnKart]):  # type: ignore
        # wrap task to prevent task name from being changed
        @luigi.task._task_wraps(task_class)
        class Wrapped(task_class):
            __is_decorated_inherits_config_params = True
            __config_params: Dict[str, Any] = dict()

            @classmethod
            def inject_config_params(cls) -> None:
                for param_key, param_value in self._config_class().param_kwargs.items():
                    task_param_key = self._parameter_alias.get(param_key, param_key)

                    if hasattr(cls, task_param_key) and task_param_key not in cls.__config_params:
                        cls.__config_params[task_param_key] = param_value

            @classmethod
            def get_param_values(cls, params, args, kwargs):  # type: ignore
                cls.__config_params.update(kwargs)
                return super(Wrapped, cls).get_param_values(params, args, cls.__config_params)

        return Wrapped
