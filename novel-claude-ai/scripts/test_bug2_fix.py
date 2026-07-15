#!/usr/bin/env python3
"""BUG-2 修复验证测试

测试环境变量配置值类型转换是否正确工作。
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import ConfigLoader, ConfigSchema, load_quality_config


def test_env_var_type_conversion():
    """测试环境变量类型转换"""
    print("=" * 60)
    print("BUG-2 修复验证测试")
    print("=" * 60)

    # 测试1: 整数类型环境变量
    print("\n测试1: 整数类型环境变量")
    test_env_var = "QUALITY_MIN_CHARS"
    test_value = "5000"

    # 设置环境变量
    os.environ[test_env_var] = test_value
    print(f"  设置环境变量: {test_env_var}={test_value}")

    # 加载配置
    config = load_quality_config()
    result = config["min_chars"]

    # 验证结果
    print(f"  预期结果: int 5000")
    print(f"  实际结果: {type(result).__name__} {result}")

    if isinstance(result, int) and result == 5000:
        print("  ✅ 测试通过: 类型转换正确")
        test1_passed = True
    else:
        print("  ❌ 测试失败: 类型转换错误")
        test1_passed = False

    # 清理环境变量
    del os.environ[test_env_var]

    # 测试2: 浮点数类型环境变量
    print("\n测试2: 浮点数类型环境变量")
    test_env_var = "QUALITY_MIN_DIALOGUE_RATIO"
    test_value = "0.05"

    # 设置环境变量
    os.environ[test_env_var] = test_value
    print(f"  设置环境变量: {test_env_var}={test_value}")

    # 重新加载配置（清除缓存）
    from config_loader import get_loader
    loader = get_loader()
    loader.reload()

    # 加载配置
    config = load_quality_config()
    result = config["min_dialogue_ratio"]

    # 验证结果
    print(f"  预期结果: float 0.05")
    print(f"  实际结果: {type(result).__name__} {result}")

    if isinstance(result, float) and result == 0.05:
        print("  ✅ 测试通过: 类型转换正确")
        test2_passed = True
    else:
        print("  ❌ 测试失败: 类型转换错误")
        test2_passed = False

    # 清理环境变量
    del os.environ[test_env_var]

    # 测试3: 布尔类型环境变量
    print("\n测试3: 布尔类型环境变量（模拟）")
    # 注意：当前Schema中没有布尔类型字段，但get_env_value支持
    print("  ⚠️ 跳过: Schema中无布尔类型字段")

    # 测试4: 验证默认值仍然工作
    print("\n测试4: 验证默认值仍然工作")
    # 不设置环境变量，应该返回默认值
    if "QUALITY_MIN_CHARS" in os.environ:
        del os.environ["QUALITY_MIN_CHARS"]

    loader.reload()
    config = load_quality_config()
    result = config["min_chars"]

    print(f"  预期结果: int 1200 (默认值)")
    print(f"  实际结果: {type(result).__name__} {result}")

    if isinstance(result, int) and result == 1200:
        print("  ✅ 测试通过: 默认值正确")
        test4_passed = True
    else:
        print("  ❌ 测试失败: 默认值错误")
        test4_passed = False

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"测试1 (整数类型): {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"测试2 (浮点数类型): {'✅ 通过' if test2_passed else '❌ 失败'}")
    print(f"测试4 (默认值): {'✅ 通过' if test4_passed else '❌ 失败'}")

    all_passed = test1_passed and test2_passed and test4_passed
    print(f"\n总结: {'✅ 所有测试通过' if all_passed else '❌ 部分测试失败'}")

    return all_passed


if __name__ == "__main__":
    success = test_env_var_type_conversion()
    sys.exit(0 if success else 1)
