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
            is_decorated_inherits_config_params = True
            __config_params: Dict[str, Any] = dict()
            __do_injection = True

            @classmethod
            def inject_config_params(cls) -> None:
                cls.__config_params.clear()  # clear config param cache
                for param_key, param_value in self._config_class().param_kwargs.items():
                    task_param_key = self._parameter_alias.get(param_key, param_key)
                    if hasattr(cls, task_param_key):
                        cls.__config_params[task_param_key] = param_value

            @classmethod
            def get_param_values(cls, params, args, kwargs):  # type: ignore
                if cls.__do_injection:
                    cls.inject_config_params()
                for param_key, param_value in cls.__config_params.items():
                    if hasattr(cls, param_key) and param_key not in kwargs:
                        kwargs[param_key] = param_value
                return super(Wrapped, cls).get_param_values(params, args, kwargs)

            @classmethod
            def set_injection_flag(cls, flag: bool):  # type: ignore
                cls.__do_injection = flag

        return Wrapped
