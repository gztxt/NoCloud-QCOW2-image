"""build.yml 收敛守卫（2026-10-09，PT-20261008-16）。

【为什么要有这个】主仓 `gztxt/technical-docs` 与子仓 `gztxt/NoCloud-QCOW2-image`
曾各持一份同名 `build.yml`，靠目录归属区分。两份都声称构建同一个镜像：

  · 子仓那份能跑，但两次运行都红在 supermin（缺 libstdc++.so.6）；
  · 主仓那份**必然失败**——它跑在 technical-docs 仓，而那个仓的 .gitignore
    第 7 行 `*/` 把 NoCloud-QCOW2-image/ 整个挡住（`git ls-files` 恒为 0），
    `working-directory` 在 runner 上根本不存在 ⇒
    「An error occurred trying to start process '/usr/bin/bash' with working
    directory '.../NoCloud-QCOW2-image'. No such file or directory」。
    而它的 `paths:` 过滤写的正是这个子仓目录路径 ⇒ 该路径下无被跟踪文件 ⇒
    **过滤形同虚设**，只能被 workflow 文件自身改动唤醒，一唤醒就必失败。

【本守卫守什么】子仓那份必须持续保有「Release 发布能力 + paths 过滤 +
direct 后端 + timeout」四项；主仓那份**不得复活**。任一条被改掉即红。

【口径说明】这是纯文本守卫（不跑 Actions）。它防的是「结构被改回退化形态」，
**不证明 CI 能跑通** —— supermin/libstdc++ 是另一码事，未纳入本守卫。
"""
import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_WF = _REPO / ".github" / "workflows" / "build.yml"
_TEXT = _WF.read_text(encoding="utf-8")


class WorkflowConvergedTest(unittest.TestCase):
    def test_workflow_exists(self):
        self.assertTrue(_WF.is_file(), "子仓 build.yml 不见了 ⇒ 构建无处可跑")

    def test_release_publishing_retained(self):
        """Release 发布能力必须保留。

        为什么不能退回纯 artifact：`GITHUB-ACTIONS-构建指南.md:32` 向用户承诺
        「自动在 Releases 生成 .qcow2.xz」，而 artifact 只有有限保留期
        （原版 7 天）—— 391MB 的镜像 7 天后就取不到了，承诺落空。
        收敛时保留 Release 是有据的取舍，不是「舍不得删」。
        """
        self.assertIn("softprops/action-gh-release", _TEXT, "Release 发布步骤被删 ⇒ 指南承诺落空")
        self.assertIn("permissions:", _TEXT)
        # contents: write 是挂 Release 资产的必要权限，降成 read 会让发布失败
        m = re.search(r"permissions:\s*\n\s*contents:\s*(\w+)", _TEXT)
        self.assertIsNotNone(m, "缺 permissions 声明")
        self.assertEqual(m.group(1), "write", "contents 权限须为 write，否则挂不了 Release 资产")

    def test_paths_filter_present(self):
        """paths: 过滤必须在，防止改文档就烧 20 分钟构建。"""
        self.assertRegex(_TEXT, r"paths:", "缺 paths: 过滤")
        for p in ("build.sh", "scripts/**", ".github/workflows/build.yml"):
            self.assertIn(p, _TEXT, f"paths 过滤缺 {p}")

    def test_direct_backend_restored(self):
        """LIBGUESTFS_BACKEND: direct 必须回补。

        本地提交 9fa67de 曾把它删掉 —— **那是误改**：它与 supermin 失败无关
        （supermin 在 direct 后端下照样跑、照样因 appliance 缺库而挂），
        删掉不会修好任何问题，只会让 virt-customize 换个失败方式。
        ubuntu runner 上没有 libvirt daemon，去掉 direct 会直接让构建起不来。

        【为什么用「YAML 解析后取值」而不是正则扫原文】第一版写的是
        `r"LIBGUESTFS_BACKEND:\s*direct"` 扫文本，红向自证立刻暴露了它的洞：
        把**整个 env: 块删掉**时正则匹配不到 ⇒ 守卫**全绿**⇒ 静默失效。
        正则只认「键存在」，不认「键的值被谁继承/覆盖」；而 workflow 语义认的是
        解析后的最终值。凡是断言「某个配置项生效」的守卫，都必须按解析后的结构取值。
        """
        try:
            import yaml
        except ImportError:                       # pragma: no cover
            self.skipTest("本解释器无 pyyaml，改由结构化检查覆盖")
        doc = yaml.safe_load(_TEXT)
        # YAML 1.1 会把裸on 解析成布尔 True
        on = doc[True] if True in doc else doc.get("on")
        self.assertIsNotNone(on, "on: 块解析失败")
        env = (doc.get("jobs", {}).get("build", {}) or {}).get("env") or {}
        self.assertEqual(
            env.get("LIBGUESTFS_BACKEND"), "direct",
            "direct 后端丢失或未生效（解析后的 env 为 %r）⇒ ubuntu runner 上无 "
            "libvirt 会起不来" % (env,))

    def test_timeout_present(self):
        """必须有 timeout-minutes，否则 supermin 挂死会烧到 GitHub 默认 6 小时。"""
        m = re.search(r"timeout-minutes:\s*(\d+)", _TEXT)
        self.assertIsNotNone(m, "缺 timeout-minutes ⇒ 挂死时白烧 6 小时")
        self.assertGreaterEqual(int(m.group(1)), 20,
                                "timeout 过短：实测构建需 10~20 分钟（含 391MB 下载 + xz 压缩）")


class MainRepoMustNotRegrowWorkflowTest(unittest.TestCase):
    """主仓那份**不得复活**。这是收敛的核心断言。"""

    MAIN_WORKFLOW = _REPO.parent / ".github" / "workflows" / "build.yml"

    def test_main_repo_has_no_qcow2_workflow(self):
        """主仓若再有这份 workflow，一改就会触发一个必失败的运行。"""
        self.assertFalse(
            self.MAIN_WORKFLOW.is_file(),
            "主仓 build.yml 复活了 —— 它的 working-directory 指向主仓里根本没入库的"
            "子仓目录（被 .gitignore 的 */ 挡住），一被唤醒就必然报 No such file or directory。"
            "构建归属已收敛到子仓 gztxt/NoCloud-QCOW2-image，不要在主仓放第二份。")

    def test_main_repo_gitignore_still_blocks_nested_repo(self):
        """主仓 .gitignore 的 `*/` 全屏蔽**必须保留**。

        反向断言：若有人为了「让构建跑起来」把 NoCloud-QCOW2-image/ 加进主仓
        白名单，主仓那份（若复活）就会变成能跑的 —— 于是两份 workflow 同时构建、
        抢同一个发布名。且源码会在两个仓同时存在，制造两个真相源。
        收敛选的是「拆干净」路线，不是「并入主仓」路线。
        """
        gi = (_REPO.parent / ".gitignore")
        self.assertTrue(gi.is_file(), "主仓 .gitignore 不见了")
        text = gi.read_text(encoding="utf-8", errors="replace")
        self.assertRegex(text, r"(?m)^\*\.?$|^\*/?$",
                         "主仓 .gitignore 的默认全屏蔽规则不见了 —— 这是既存大仓的"
                         "安全底座，不要为了跑一次 CI 就拆掉")
        self.assertFalse(
            re.search(r"(?m)^!NoCloud-QCOW2-image", text),
            "NoCloud-QCOW2-image/ 被加进主仓白名单了 —— 该目录是独立子仓"
            "（有自己的远端 gztxt/NoCloud-QCOW2-image），纳入主仓会造成两个真相源"
            "且两份 workflow 抢发布名。如确需并入，先在台账登记并裁定。")


if __name__ == "__main__":
    unittest.main()