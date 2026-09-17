---
name: tdd-plan
description: "Create an implementation plan when test-first TDD is requested, pairing each behavior test with its implementation."
---

# TDD Implementation Plan

このスキルは、実装計画をTDD（テスト駆動開発）の原則に従って構成します。

## Core Principle

**1テスト → 1実装の細粒度サイクル**

各テストファイルを書いたら、すぐにそのテストを通す実装を書く。
全テストをまとめて書いてから全実装を書くのではない。

## Plan Structure (Fine-Grained TDD Cycles)

### ✅ Correct: 細粒度サイクル

| Step | Phase | Content |
|------|-------|---------|
| 1 | RED | test_feature_a.py - 失敗するテスト |
| 2 | GREEN | feature_a.py - テストを通す実装 |
| 3 | RED | test_feature_b.py - 失敗するテスト |
| 4 | GREEN | feature_b.py - テストを通す実装 |
| ... | ... | ... |
| N | REFACTOR | Cleanup, import更新, 旧ファイル削除 |

### ❌ Wrong: 大粒度（避けるべき）

| Step | Content | Problem |
|------|---------|---------|
| 1 | 全テストファイル | サイクルが大きすぎる |
| 2 | 全実装ファイル | フィードバックが遅い |

## Plan Template

```
# Plan: [Feature Name]

## 概要
[このプランで達成すること]

---

## TDD実装ステップ（細粒度）

### Step 1: テスト - FeatureA

**作成**: `tests/unit/feature_a/test_feature_a.py`

**テスト観点**:
- 正常系: 有効な入力で期待する結果が返る
- 異常系: 無効な入力でエラーが発生する
- 境界値: 空文字、最大長など

**確認**: `pytest tests/unit/feature_a/test_feature_a.py -v`
**期待結果**: ModuleNotFoundError で失敗（RED）

---

### Step 2: 実装 - FeatureA

**作成**: `src/feature_a/feature_a.py`
- 内容の説明

**確認**: `pytest tests/unit/feature_a/test_feature_a.py -v`
**期待結果**: 全テスト成功（GREEN）

---

### Step 3: テスト - FeatureB
...

### Step 4: 実装 - FeatureB
...

### Step N: Cleanup / Refactor

**削除/修正**: 旧ファイル、import更新など

**確認**: `pytest tests/unit/ -v`
**期待結果**: 全テスト成功
```

## Checklist Before Completing Plan

- [ ] 各テストファイルの直後に対応する実装ファイルがある
- [ ] 各テストステップにテスト観点が箇条書きで記載されている
- [ ] 各ステップに確認コマンドと期待結果がある
- [ ] RED（失敗）→ GREEN（成功）の流れが明確
- [ ] 最後にCleanup/Refactorステップがある

## Notes

- 依存関係がある場合は、依存される側を先に実装
- 各ステップは独立して実行・検証可能に
- ステップ数が多くなっても、細粒度を維持する
