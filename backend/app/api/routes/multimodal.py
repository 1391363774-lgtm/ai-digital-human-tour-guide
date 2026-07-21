from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.response import success
from app.services.multimodal_service import MultimodalGuideService, get_multimodal_capability

router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])


@router.get("/capability")
def capability():
    return success(get_multimodal_capability())


@router.post("/image-question")
async def image_question(
    image: UploadFile = File(...),
    question: str = Form(default=""),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    result = MultimodalGuideService().analyze_image(image_bytes, image.content_type, question)
    return success(result.__dict__)
