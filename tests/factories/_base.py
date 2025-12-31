"""
_base.py - Factory Boy 基类

提供适配 Pydantic V2 模型的 Factory Boy 基类，确保模型实例化时参数作为关键字参数传递。
"""

import factory
from typing import Any, Type


class PydanticModelFactory(factory.Factory): # type: ignore
    """
    适配 Pydantic V2 模型的 Factory Boy 基类

    这个基类确保 Factory Boy 在实例化 Pydantic 模型时，将参数作为关键字参数传递给模型的 __init__ 方法，
    而不是直接赋值属性。这对于 Pydantic 模型的正确初始化至关重要。
    """
    
    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class: Type, *args: Any, **kwargs: Any):
        """
        重写 _create 方法，确保参数作为关键字参数传递给 Pydantic 模型

        Args:
            model_class: 要实例化的 Pydantic 模型类
            *args: 位置参数（将被忽略，因为 Pydantic 模型主要使用关键字参数）
            **kwargs: 关键字参数，将传递给模型的 __init__ 方法

        Returns:
            实例化的 Pydantic 模型对象
        """
        # 对于 Pydantic 模型，我们只传递关键字参数
        # 位置参数将被忽略，因为 Pydantic V2 主要使用关键字参数
        return model_class(**kwargs)
