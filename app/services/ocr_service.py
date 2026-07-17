from app.core.exceptions import OCRFailed
class NoOpOCRProvider:
    async def extract(self,*_): raise OCRFailed()
