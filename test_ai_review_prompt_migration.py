from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from term_extractor_app.ai_review import database as db, prompt_service as prompts
from term_extractor_app.ai_review.review_service import _build_user_prompt, _prompt_signature


# Verbatim defaults from v2.2.9, kept independently of the new prompt constants.
OLD_SYSTEM = "你是专业翻译审校，请检查译文是否准确、自然、完整，并只输出符合要求的 JSON。"
OLD_USER = """请审校以下 JSON 条目，返回严格 JSON，不要输出额外解释。

要求：
1. 返回格式必须是 {"items":[...]}。
2. 每个条目必须包含 id、has_issue、issue_type、issue、suggestion。
3. 如果没有问题，has_issue 为 false，issue_type、issue、suggestion 返回空字符串。
4. 如果有问题，issue_type 用简洁分类，例如漏译、错译、语法问题、格式问题、语义不清。这些只是问题归类标签，不是额外检查清单，不要因为标签示例而扩大审校范围。
5. 如果有问题，suggestion 必须只填写完整修改后的译文句子，不要解释，不要写修改理由，不要只写片段。
6. 如果条目包含 info 字段，请把 info 作为参考信息；info 中 category 是信息类别，value 是信息内容。
7. 如果条目不包含 info 字段，不要假设存在参考信息。

{term_review}

待审校 JSON：
{text}"""


class PromptMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, "DB_PATH", Path(self.temp.name) / "review.sqlite3")
        self.patch.start()
        db.init_db()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def seed(self, system=OLD_SYSTEM, user=OLD_USER, *, is_default=1, template_id="existing"):
        with db.get_connection() as conn:
            conn.execute(
                """INSERT INTO prompt_templates
                (id, name, system_prompt, user_prompt, forbidden_words_text, is_default, created_at, updated_at)
                VALUES (?, 'kept name', ?, ?, 'kept words', ?, 'created', 'updated')""",
                (template_id, system, user, is_default),
            )
        return template_id

    def test_fresh_install_and_explicit_reset_use_new_defaults(self):
        fresh = prompts.get_prompt_template()
        self.assertEqual(fresh["system_prompt"], prompts.DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(fresh["user_prompt"], prompts.DEFAULT_USER_PROMPT)
        prompts.save_prompt_template(template_id=fresh["id"], name="custom", system_prompt="mine", user_prompt="{text}")
        reset = prompts.reset_default_prompt_template()
        self.assertEqual(reset["id"], fresh["id"])
        self.assertEqual(reset["system_prompt"], prompts.DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(reset["user_prompt"], prompts.DEFAULT_USER_PROMPT)

    def test_unchanged_default_migrates_in_place_and_is_idempotent(self):
        self.seed()
        migrated = prompts.get_prompt_template()
        self.assertEqual(migrated["id"], "existing")
        self.assertEqual(migrated["name"], "kept name")
        self.assertEqual(migrated["forbidden_words_text"], "kept words")
        self.assertEqual(migrated["created_at"], "created")
        self.assertEqual(migrated["system_prompt"], prompts.DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(migrated["user_prompt"], prompts.DEFAULT_USER_PROMPT)
        with patch.object(prompts, "utc_now", return_value="must not rewrite"):
            self.assertEqual(prompts.get_prompt_template(), migrated)

    def test_older_default_without_term_placeholder_also_migrates(self):
        self.seed(user=OLD_USER.replace("{term_review}\n\n", ""))
        self.assertEqual(prompts.get_prompt_template()["user_prompt"], prompts.DEFAULT_USER_PROMPT)

    def test_windows_newlines_in_unchanged_default_migrate(self):
        self.seed(user=OLD_USER.replace("\n", "\r\n"))
        self.assertEqual(prompts.get_prompt_template()["user_prompt"], prompts.DEFAULT_USER_PROMPT)

    def test_customized_default_is_never_overwritten(self):
        cases = [
            (OLD_SYSTEM + "只检查漏译。", OLD_USER),
            (OLD_SYSTEM, OLD_USER + "\n只检查漏译。"),
            (OLD_SYSTEM, "我的自定义要求\n{text}"),  # No marker: used to be overwritten.
            (OLD_SYSTEM, OLD_USER + " "),
            (prompts.DEFAULT_SYSTEM_PROMPT, OLD_USER),
        ]
        for system, user in cases:
            with self.subTest(system=system, user=user):
                with db.get_connection() as conn:
                    conn.execute("DELETE FROM prompt_templates")
                self.seed(system, user)
                saved = prompts.get_prompt_template()
                self.assertEqual((saved["system_prompt"], saved["user_prompt"]), (system, user))
                self.assertEqual(saved["updated_at"], "updated")

    def test_nondefault_templates_are_preserved_even_if_their_text_is_old_default(self):
        self.seed(is_default=0, template_id="copy")
        templates = prompts.list_prompt_templates()
        copied = next(template for template in templates if template["id"] == "copy")
        self.assertEqual((copied["system_prompt"], copied["user_prompt"]), (OLD_SYSTEM, OLD_USER))
        self.assertEqual(len(templates), 2)

    def test_request_uses_new_classification_and_invalidates_old_cache(self):
        template = prompts.get_prompt_template()
        request = _build_user_prompt(template, '{"items":[]}', has_info=False)
        self.assertIn("issue_type 根据实际发现的错误自行归纳简洁、准确的中文分类。", request)
        self.assertIn("分类包括但不限于：错字、语法错误、漏译、多译、错译、术语错误、标点错误、格式错误、Tag错误等。", request)
        self.assertNotIn("{term_review}", request)
        self.assertNotIn("{text}", request)
        self.assertIn('{"items":[]}', request)
        self.assertNotEqual(
            _prompt_signature(OLD_SYSTEM, OLD_USER, "eng", "jpn"),
            _prompt_signature(template["system_prompt"], template["user_prompt"], "eng", "jpn"),
        )


if __name__ == "__main__":
    unittest.main()
