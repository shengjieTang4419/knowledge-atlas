---
领域: Java多线程
类型: 实体·机制
---

# MESI 缓存一致性协议

## 一句话
CPU 多核缓存保持一致性的硬件协议，volatile 可见性的底层支撑。

## 是什么（骨架）
- 缓存行四态：Modified / Exclusive / Shared / Invalid
- 嗅探总线 + 状态迁移保证一致性
- volatile 写触发总线锁 / 缓存失效

## 关系
- 前置 ← [[volatile]]、[[JMM内存模型]]

## 待深挖
- [ ] MESI 状态机完整迁移表
