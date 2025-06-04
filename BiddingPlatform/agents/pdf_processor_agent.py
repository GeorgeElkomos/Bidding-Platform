from typing import Dict, Any, List, Optional
import asyncio
import io
import re

from .base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from utils.pdf_text import pdf_to_arabic_text


class PDFProcessorAgent(BaseAgent):
    """Agent specialized in processing PDF documents and extracting Arabic text."""

    # ------------------------------------------------------------------ #
    #  Construction & capabilities
    # ------------------------------------------------------------------ #
    def __init__(self, agent_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id, config)
        self.max_concurrent_pdfs = (config or {}).get("max_concurrent_pdfs", 3)

    def get_capabilities(self) -> List[str]:
        return [
            "pdf_text_extraction",
            "arabic_text_processing",
            "batch_pdf_processing",
            "text_quality_validation",
        ]

    # ------------------------------------------------------------------ #
    #  Public task entry
    # ------------------------------------------------------------------ #
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Route tasks to the appropriate internal handler."""
        task_type = task.input_data.get("task_type")

        if task_type == "extract_terms":
            return await self._extract_terms_pdf(task)
        if task_type == "extract_proposals":
            return await self._extract_proposals_batch(task)
        if task_type == "extract_single_pdf":
            return await self._extract_single_pdf(task)

        raise ValueError(f"PDFProcessorAgent: لم أتعرف على نوع المهمة '{task_type}'")

    # ------------------------------------------------------------------ #
    #  1) Terms & specifications PDF
    # ------------------------------------------------------------------ #
    async def _extract_terms_pdf(self, task: AgentTask) -> AgentResult:
        """Extract text from a terms/specifications PDF with robust fallbacks."""
        pdf_file = task.input_data.get("pdf_file")
        if not pdf_file:
            raise ValueError(
                "لم يتم إرفاق ملف PDF الخاص بكراسة الشروط.\n"
                "⚠️ تذكير: تأكد من رفع ملف غير محمي بكلمة مرور ومن أنه قابل للبحث (ليس مسحًا ضوئيًا فقط)."
            )

        try:
            text = self._extract_text_with_fallbacks(pdf_file, "terms.pdf")

            if not text.strip():
                raise ValueError(
                    "تعذّر استخراج أي نص من كراسة الشروط.\n"
                    "🔍 ربما يكون الملف عبارة عن صور ممسوحة ضوئيًا أو محميًا بكلمة مرور.\n"
                    "💡 جرّب تفعيل OCR قبل الرفع أو أزل الحماية عن الملف."
                )

            arabic_ratio = self._calculate_arabic_ratio(text)
            self.logger.info(
                f"[Terms PDF] Extraction succeeded: {len(text)} chars "
                f"(Arabic ratio = {arabic_ratio:.2%})"
            )

            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                output_data={
                    "text": text,
                    "text_length": len(text),
                    "arabic_ratio": arabic_ratio,
                    "quality_score": self._assess_text_quality(text),
                },
            )

        except Exception as exc:
            self.logger.error(f"[Terms PDF] Extraction failed: {exc}")
            raise ValueError(
                f"فشل استخراج نص كراسة الشروط:\n{exc}\n"
                "🚑 خطوات مقترحة: تأكد من أن الملف غير تالف، غير محمي، وقابل للبحث أو استخدم OCR."
            )

    # ------------------------------------------------------------------ #
    #  2) Core extraction with fallbacks
    # ------------------------------------------------------------------ #
    def _extract_text_with_fallbacks(self, pdf_file, friendly_name: str) -> str:
        """Attempt multiple extraction strategies before giving up."""
        # Handle FastAPI UploadFile / Django InMemoryUploadedFile, etc.
        stream = pdf_file.file if hasattr(pdf_file, "file") else pdf_file

        # Strategy #1: primary util
        if hasattr(stream, "seek"):
            stream.seek(0)
        text = pdf_to_arabic_text(stream)
        if text.strip():
            return text

        # Strategy #2: retry after full reset (sometimes fixes encoding glitches)
        if hasattr(stream, "seek"):
            stream.seek(0)
        text = pdf_to_arabic_text(stream)
        if text.strip():
            return text

        # Strategy #3: granular per-page extraction via PyMuPDF
        try:
            import fitz  # lazy import
            if hasattr(stream, "seek"):
                stream.seek(0)
            data = stream.read() if hasattr(stream, "read") else stream
            doc = fitz.open(stream=data, filetype="pdf")
            blocks: List[str] = []

            for pno in range(doc.page_count):
                page = doc[pno]
                # 3-A: default text
                page_text = page.get_text()
                if not page_text.strip():
                    # 3-B: raw text only
                    page_text = page.get_text("text")
                if not page_text.strip():
                    # 3-C: iterate spans (more granular)
                    try:
                        for blk in page.get_text("dict")["blocks"]:
                            for line in blk.get("lines", []):
                                for span in line.get("spans", []):
                                    blocks.append(span.get("text", ""))
                    except Exception:
                        # 3-D: last resort – textpage walker
                        page_text = page.get_textpage().extractText()
                        blocks.append(page_text)
                else:
                    blocks.append(page_text)

            doc.close()
            combined = " ".join(blocks).strip()
            if combined:
                return combined

        except Exception as fallback_exc:
            self.logger.warning(
                f"[{friendly_name}] Fallback PyMuPDF extraction error: {fallback_exc}"
            )

        raise ValueError(
            f"جميع طرق الاستخراج فشلت لملف «{friendly_name}».\n"
            "قد يكون ملفًا مصورًا (Scanned) أو تالفًا أو محميًا بكلمة مرور."
        )

    # ------------------------------------------------------------------ #
    #  3) Batch proposals extraction
    # ------------------------------------------------------------------ #
    async def _extract_proposals_batch(self, task: AgentTask) -> AgentResult:
        """Extract text from multiple proposals with concurrency limits."""
        proposals = task.input_data.get("proposals", [])
        if not proposals:
            raise ValueError("🚫 لم يتم إرفاق أي ملفات عروض (proposals) لمعالجتها.")

        sem = asyncio.Semaphore(self.max_concurrent_pdfs)
        coroutines = [self._extract_single_proposal_with_semaphore(sem, p) for p in proposals]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        successes, failures = [], []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                failures.append({"filename": proposals[i].filename, "error": str(res)})
            else:
                successes.append(res)

        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                "successful_extractions": successes,
                "failed_extractions": failures,
                "success_count": len(successes),
                "failure_count": len(failures),
            },
        )

    async def _extract_single_proposal_with_semaphore(self, sem: asyncio.Semaphore, proposal):
        """Wrapper to enforce semaphore limits."""
        async with sem:
            return await self._extract_single_proposal(proposal)

    async def _extract_single_proposal(self, proposal) -> Dict[str, Any]:
        """Extract text from a single proposal; raises detailed errors."""
        filename = proposal.filename
        company = filename.rsplit(".", 1)[0]

        stream = proposal.file if hasattr(proposal, "file") else proposal
        if hasattr(stream, "seek"):
            stream.seek(0)

        text = pdf_to_arabic_text(stream)
        if not text.strip():
            raise ValueError(
                f"❌ تعذّر استخراج نص من ملف العرض «{filename}».\n"
                "تحقّق من أنه قابل للبحث أو استخدم OCR."
            )

        return {
            "company_name": company,
            "filename": filename,
            "pdf_text": text,
            "text_length": len(text),
            "arabic_ratio": self._calculate_arabic_ratio(text),
            "quality_score": self._assess_text_quality(text),
        }

    # ------------------------------------------------------------------ #
    #  4) Single PDF generic
    # ------------------------------------------------------------------ #
    async def _extract_single_pdf(self, task: AgentTask) -> AgentResult:
        """Generic extractor for a single PDF file (non-proposal)."""
        pdf_file = task.input_data.get("pdf_file")
        filename = task.input_data.get("filename", "unknown.pdf")
        if not pdf_file:
            raise ValueError("لم يتم إرفاق ملف PDF للمعالجة.")

        stream = pdf_file.file if hasattr(pdf_file, "file") else pdf_file
        if hasattr(stream, "seek"):
            stream.seek(0)

        text = pdf_to_arabic_text(stream)
        if not text.strip():
            raise ValueError(
                f"لم يتم العثور على نص في «{filename}» – ربما يكون الملف ممسوحًا ضوئيًا."
            )

        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=AgentStatus.COMPLETED,
            output_data={
                "filename": filename,
                "text": text,
                "text_length": len(text),
                "arabic_ratio": self._calculate_arabic_ratio(text),
                "quality_score": self._assess_text_quality(text),
            },
        )

    # ------------------------------------------------------------------ #
    #  Utility metrics
    # ------------------------------------------------------------------ #
    @staticmethod
    def _calculate_arabic_ratio(text: str) -> float:
        """Return the proportion of Arabic letters in the extracted text."""
        arabic = re.findall(r"[\u0600-\u06FF]", text)
        alpha = [c for c in text if c.isalpha()]
        return len(arabic) / max(len(alpha), 1)

    def _assess_text_quality(self, text: str) -> float:
        """Compute a simple 0-1 quality score for extracted text."""
        if not text:
            return 0.0

        arabic_ratio = self._calculate_arabic_ratio(text)
        length_score = min(len(text) / 1000, 1.0)
        sentence_score = min(len(re.findall(r"[.!?؟]", text)) / 10, 1.0)
        whitespace_ratio = len(re.findall(r"\s", text)) / len(text)
        whitespace_penalty = 1.0 - min(whitespace_ratio / 0.30, 1.0)

        score = (
            arabic_ratio * 0.4
            + length_score * 0.3
            + sentence_score * 0.2
            + whitespace_penalty * 0.1
        )
        return round(score, 3)
