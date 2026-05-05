import unittest
from uuid import uuid4

from app.application.exceptions import AIProviderEmptyResponseError
from app.application.use_cases.chat_cv import (
    ChatCVUseCase,
    SAFE_EMPTY_AI_MESSAGE,
    SAFE_INVALID_CV_MESSAGE,
)
from app.infrastructure.ai.openai_service import OpenAIService


class FakeRepo:
    def __init__(self):
        self.created = []
        self.saved_messages = []

    async def create(self, cv_entity):
        if not getattr(cv_entity, "id", None):
            cv_entity.id = uuid4()
        self.created.append(cv_entity)
        return cv_entity

    async def create_versioned(self, **kwargs):
        raise AssertionError("create_versioned should not be called in these tests")

    async def save_chat_messages(self, conversation_id, user_id, messages):
        self.saved_messages.append(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "messages": messages,
            }
        )


class EmptyAI:
    async def chat_interaction(self, messages):
        raise AIProviderEmptyResponseError("AI provider returned an empty response")

    async def chat_interaction_stream(self, messages):
        if False:
            yield ""


class InvalidCVAI:
    async def chat_interaction(self, messages):
        return "Đây là CV:\n<FINAL_CV>OK</FINAL_CV>"

    async def chat_interaction_stream(self, messages):
        yield "Đây là CV:\n<FINAL_CV>OK</FINAL_CV>"


class ValidCVAI:
    async def chat_interaction(self, messages):
        return f"Đã tạo CV.\n<FINAL_CV>{VALID_CV}</FINAL_CV>"

    async def chat_interaction_stream(self, messages):
        yield "Đã tạo CV.\n<FINAL_CV>"
        yield VALID_CV
        yield "</FINAL_CV>"


class FakeOpenAIClient:
    class Chat:
        class Completions:
            @staticmethod
            def create(**kwargs):
                class Message:
                    content = None

                class Choice:
                    message = Message()

                class Response:
                    choices = [Choice()]

                return Response()

        completions = Completions()

    chat = Chat()


VALID_CV = """# Nguyễn Văn A
Software Engineer | [Email] | [Số điện thoại]

## SUMMARY
Software Engineer tập trung vào phát triển sản phẩm web, backend API và tối ưu trải nghiệm người dùng.

## SKILLS
- Python
- React
- PostgreSQL

## EXPERIENCE
- Xây dựng API và giao diện web theo yêu cầu sản phẩm.

## EDUCATION
- [Trường đại học] | [Ngành học]
"""


class ChatCVSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_chat_empty_content_raises_without_mock_cv(self):
        service = OpenAIService.__new__(OpenAIService)
        service._client = FakeOpenAIClient()
        service._model = "test-model"

        with self.assertRaises(AIProviderEmptyResponseError):
            await service.chat_interaction([{"role": "user", "content": "Tạo CV theo JD React"}])

    async def test_empty_ai_response_returns_safe_message_and_does_not_save_cv(self):
        repo = FakeRepo()
        use_case = ChatCVUseCase(repo, EmptyAI())

        reply, cv_id, _ = await use_case.execute(
            user_id=uuid4(),
            messages=[{"role": "user", "content": "Tạo CV Software Engineer"}],
        )

        self.assertEqual(reply, SAFE_EMPTY_AI_MESSAGE)
        self.assertIsNone(cv_id)
        self.assertEqual(repo.created, [])
        self.assertEqual(repo.saved_messages[-1]["messages"][-1]["content"], SAFE_EMPTY_AI_MESSAGE)

    async def test_invalid_final_cv_is_not_saved(self):
        repo = FakeRepo()
        use_case = ChatCVUseCase(repo, InvalidCVAI())

        reply, cv_id, _ = await use_case.execute(
            user_id=uuid4(),
            messages=[{"role": "user", "content": "Tạo CV Software Engineer"}],
        )

        self.assertEqual(reply, SAFE_INVALID_CV_MESSAGE)
        self.assertIsNone(cv_id)
        self.assertEqual(repo.created, [])
        self.assertEqual(repo.saved_messages[-1]["messages"][-1]["content"], SAFE_INVALID_CV_MESSAGE)

    async def test_valid_final_cv_is_saved(self):
        repo = FakeRepo()
        use_case = ChatCVUseCase(repo, ValidCVAI())

        reply, cv_id, _ = await use_case.execute(
            user_id=uuid4(),
            messages=[{"role": "user", "content": "Tạo CV Software Engineer"}],
        )

        self.assertEqual(reply, "Đã tạo CV.\n\n*(Đã tạo CV thành công)*")
        self.assertIsNotNone(cv_id)
        self.assertEqual(len(repo.created), 1)
        self.assertIn("## SKILLS", repo.created[0].generated_content["content"])

    async def test_empty_stream_returns_safe_message_and_does_not_save_cv(self):
        repo = FakeRepo()
        use_case = ChatCVUseCase(repo, EmptyAI())

        events = []
        async for chunk in use_case.execute_stream(
            user_id=uuid4(),
            messages=[{"role": "user", "content": "Tạo CV Software Engineer"}],
        ):
            events.append(chunk)

        joined = "".join(events)
        self.assertIn("event: chat_chunk", joined)
        self.assertNotIn("event: cv_id", joined)
        self.assertEqual(repo.created, [])
        self.assertEqual(repo.saved_messages[-1]["messages"][-1]["content"], SAFE_EMPTY_AI_MESSAGE)


if __name__ == "__main__":
    unittest.main()
