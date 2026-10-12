---
领域: Java多线程
类型: 实体·概念
---

# JMM 内存模型

## 一句话
定义 Java 线程间内存交互的抽象规则（happens-before），是多线程正确性的地基。

## 是什么（骨架）
- 主内存 + 工作内存的抽象
- happens-before 规则：程序顺序 / volatile / 锁 / 传递性
- 解决三件事：可见性、有序性、原子性

## 关系
- 递进 → [[volatile]]（JMM 的关键字级实现）
- 递进 → [[MESI缓存一致性协议]]（可见性的硬件底层）

## 挂载
- 可信源：JSR-133 / JLS §17、Goetz《Java 并发编程实战》

## 待深挖
- [ ] happens-before 完整规则表
