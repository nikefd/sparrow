# 如何发布到 PyPI

> 讲版本号、CI、以及 tag → PyPI 的自动发布流程。源文件：`.github/workflows/`、
> `pyproject.toml`。

## 一句话流程

**改版本号 → 合进 main → 打 `v<version>` tag 并 push → GitHub Actions 自动测试、
构建、发布到 PyPI、建 GitHub Release。** 仓库不存任何 PyPI token。

## CI（每次 push / PR）

`.github/workflows/ci.yml`：在 `main` 的 push、对 `main` 的 PR、手动触发时，跨
Python **3.9 / 3.11 / 3.12** 矩阵跑 `pip install -e ".[dev]"` + `python -m pytest -q`。
引擎仅 stdlib，所以多版本测试很轻。

## 发布（push tag `v*`）

`.github/workflows/release.yml` 在 push 形如 `v0.2.0` 的 tag 时触发，串成一条
带门禁的流水线：

| Job | 做什么 | 门禁 |
|---|---|---|
| `validate-tag` | 校验 tag 所在 commit 是 `main` 的祖先 | **不在 main 上的 tag 直接失败**，杜绝从特性分支发版 |
| `test` | 跨 3.9/3.11/3.12 跑 pytest | 任一失败则不发布 |
| `build` | 校验 tag 版本号 == `pyproject.toml` 的 version，再 `python -m build` | **tag 与包版本不一致直接失败** |
| `publish-pypi` | `pypa/gh-action-pypi-publish` 发到 PyPI | 走 `pypi` environment（可在仓库设置加保护） |
| `github-release` | `softprops/action-gh-release` 建 Release，自动生成 notes + 附 dist | — |

发布用 **PyPI Trusted Publishing（OIDC）**：`permissions.id-token: write` 换取
临时凭证，仓库**不存 API token**。

## 发版步骤（实操）

1. 改 `pyproject.toml` 的 `version`（如 `0.2.0` → `0.2.1`）。同时确认
   `sparrow/__init__.py` 的 `__version__` 同步——两处都要改。
2. commit、合进 `main`。
3. 打 tag 并 push（tag 数字必须与 `pyproject.toml` 版本一致，否则 `build` job 失败）：

   ```bash
   git tag v0.2.1
   git push origin v0.2.1
   ```

4. 去 Actions 看 `Release` 流水线，绿了即已发到 PyPI 并建好 GitHub Release。

> **坑**：`pyproject.toml` 的 `version` 与 `__init__.py` 的 `__version__` 是两处独立
> 维护的版本号，发版前务必一起改。`build` job 只校验 tag vs `pyproject.toml`，不会
> 帮你抓 `__version__` 漏改。

## 打包内容

`pyproject.toml` 用 setuptools，`packages.find` 收 `sparrow*`，
`package-data` 把 `sparrow/web/*.js`、`*.md` 一起打进 wheel。`MANIFEST.in` 额外把
LICENSE、双语 README、examples 收进 sdist。
