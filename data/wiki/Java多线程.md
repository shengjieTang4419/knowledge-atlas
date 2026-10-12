# Java 多线程（namespace MOC）

> 第二个 namespace 样例。演示完整链路：topic → 可信源 → 实体关系梳理 → 挂全局图谱。

## topic
Java 多线程 —— 内存可见性

## 可信源（AI 筛选，低风险高信号）
- JSR-133 / JLS §17（官方规范）
- 《Java 并发编程实战》（Brian Goetz）
- OpenJDK 源码：`java.util.concurrent`、`sun.misc.Unsafe`
- Doug Lea 并发文档

## 实体（本 namespace）
- [[JMM内存模型]] — happens-before 抽象规则
- [[volatile]] — 可见性 / 有序性
- [[MESI缓存一致性协议]] — 可见性的硬件底层

## 递进链（竖线·深度）
```mermaid
graph LR
  A[JMM内存模型] -->|递进| B[volatile]
  B -->|递进| C[MESI缓存一致性协议]
```

## 全局边（横线·广度，见 global-graph/edges.md）
- 借鉴：InnoDB 刷盘 → 定时任务批量写（跨域机制迁移）
