import base64
import io
from typing import ClassVar

from PIL import Image
from pydantic import BaseModel, Field, JsonValue, TypeAdapter, ValidationError

from osint_harness.settings import Settings
from osint_harness.transport import Transport


class _FunctionCall(BaseModel):
    arguments: str


class _ToolCall(BaseModel):
    function: _FunctionCall


class _OcrMessage(BaseModel):
    tool_calls: list[_ToolCall] = Field(min_length=1)


class _OcrChoice(BaseModel):
    message: _OcrMessage


class _OcrReply(BaseModel):
    choices: list[_OcrChoice] = Field(min_length=1)


class _OcrBlock(BaseModel):
    text: str = ""


class NemotronParseOcr:
    """Layout-aware OCR via NVIDIA nemotron-parse; tall images are tiled so text keeps its resolution."""

    URL: ClassVar[str] = "https://integrate.api.nvidia.com/v1/chat/completions"
    TILE_ASPECT: ClassVar[float] = 1.4
    MAX_SIDE: ClassVar[int] = 3300
    BLOCKS: ClassVar[TypeAdapter[list[_OcrBlock] | list[list[_OcrBlock]]]] = TypeAdapter(
        list[_OcrBlock] | list[list[_OcrBlock]]
    )

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._model = settings.ocr_model
        self._headers = {"Authorization": f"Bearer {settings.nvidia_api_key}"}

    async def transcribe(self, image: Image.Image) -> str:
        rgb = image.convert("RGB")
        pieces = [await self._transcribe_tile(tile) for tile in self._tiles(rgb)]
        return "\n\n".join(piece for piece in pieces if piece.strip())

    def _tiles(self, image: Image.Image) -> list[Image.Image]:
        width, height = image.size
        tile_height = int(width * self.TILE_ASPECT)
        if height <= tile_height * 1.15:
            return [image]
        overlap = tile_height // 10
        tops = range(0, height - overlap, tile_height - overlap)
        return [image.crop((0, top, width, min(top + tile_height, height))) for top in tops]

    async def _transcribe_tile(self, tile: Image.Image) -> str:
        tile.thumbnail((self.MAX_SIDE, self.MAX_SIDE))
        buffer = io.BytesIO()
        tile.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()
        payload: JsonValue = {
            "model": self._model,
            "messages": [{"role": "user", "content": f'<img src="data:image/png;base64,{encoded}" />'}],
            "tools": [{"type": "function", "function": {"name": "markdown_no_bbox"}}],
            "tool_choice": {"type": "function", "function": {"name": "markdown_no_bbox"}},
        }
        reply = await self._transport.post_model(self.URL, payload, self._headers, _OcrReply)
        calls = reply.choices[0].message.tool_calls
        try:
            return "\n\n".join(self._blocks_text(call.function.arguments) for call in calls)
        except ValidationError:
            self._transport.forget_post(self.URL, payload)
            raise

    @classmethod
    def _blocks_text(cls, arguments: str) -> str:
        """Raises ValidationError when the model's tool arguments are not text blocks."""
        parsed = cls.BLOCKS.validate_json(arguments)
        blocks = [item for entry in parsed for item in (entry if isinstance(entry, list) else [entry])]
        return "\n\n".join(block.text for block in blocks)
