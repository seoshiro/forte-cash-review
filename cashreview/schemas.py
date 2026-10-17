from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
import base64
from io import BytesIO
from PIL import Image


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    timestamp_sec: float = Field(ge=0)
    image_base64: str

    @model_validator(mode="after")
    def jpeg(self):
        data = base64.b64decode(self.image_base64, validate=True)
        with Image.open(BytesIO(data)) as im:
            if im.format != "JPEG":
                raise ValueError("Evidence must be JPEG")
            im.verify()
        return self


class Violation(Strict):
    type: str
    timecode_sec: float = Field(ge=0)
    description: str
    evidence_frames: list[Evidence] = Field(min_length=1, max_length=3)


class Done(Strict):
    job_id: str
    status: Literal["done"] = "done"
    verdict: Literal["violation", "no_violation"]
    violations: list[Violation]

    @model_validator(mode="after")
    def consistent(self):
        if (self.verdict == "violation") != bool(self.violations):
            raise ValueError("Verdict and events disagree")
        return self
