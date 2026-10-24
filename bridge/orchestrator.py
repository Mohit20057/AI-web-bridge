"""Orchestrator for AI Web Bridge: prompt building, AI dispatch, verification, fixer loop, and history."""

import asyncio
import hashlib
import json
import os
import re
import secrets
import string
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

from envelope import (
    BRIDGE_START,
    BRIDGE_END,
    CONTINUATION_PROMPT,
    BridgeResponse,
    build_prompt_envelope,
    extract_bridge_payload,
    stitch_continuation,
)
from handoff import HandoffManager, sanitize_secrets
from repo_context import build_repo_context, build_repo_map
from verifier import (
    apply_patch_or_fallback,
    format_fixer_prompt,
    run_verification,
)
from council import (
    build_council_round1_prompt,
    build_council_round2_prompt,
)


@dataclass
class StageResult:
    job_id: str
    stage_num: int
    total_stages: int
    provider: str
    role: str
    out_file: str
    lines_written: int
    status: str  # COMPLETE, NEEDS_INPUT, BLOCKED, FAIL
    verify: str  # PASS, FAIL, none
    summary: str
    error: str = ""
    extracted_text: str = ""


class BridgeOrchestrator:
    """Coordinates prompt construction, multi-stage relays, verification loops, and ledger logging."""

    def __init__(
        self,
        project_dir: Path | str | None = None,
        query_executor: Callable[..., Coroutine[Any, Any, str]] | None = None,
        prompts_dir: Path | str | None = None,
    ):
        self.project_dir = Path(project_dir or Path.cwd()).resolve()
        self.handoff_mgr = HandoffManager(self.project_dir)
        self.query_executor = query_executor
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir).resolve()
        else:
            repo_prompts = self.project_dir / "prompts"
            package_prompts = Path(__file__).resolve().parent.parent / "prompts"
            self.prompts_dir = repo_prompts if repo_prompts.exists() else package_prompts
        self.cache_dir = self.project_dir / ".bridge" / "cache"

    def ensure_dirs(self) -> None:
        self.handoff_mgr.ensure_dirs()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_prompt_template(self, name: str) -> str:
        """Load role template from prompts/{name}.txt or direct file path."""
        p = Path(name)
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore").strip()

        candidate = self.prompts_dir / f"{name}.txt"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="ignore").strip()

        # Try without extension
        candidate_no_ext = self.prompts_dir / name
        if candidate_no_ext.is_file():
            return candidate_no_ext.read_text(encoding="utf-8", errors="ignore").strip()

        return ""

    def _get_cache(self, key: str) -> str | None:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.is_file():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return data.get("response")
            except Exception:
                pass
        return None

    def _set_cache(self, key: str, response: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps({"response": response}, indent=2), encoding="utf-8")

    def _write_log(self, job_id: str, content: str) -> None:
        self.ensure_dirs()
        clean_content = sanitize_secrets(content, self.project_dir)
        log_file = self.project_dir / ".bridge" / "logs" / f"{job_id}.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}]\n{clean_content}\n" + "=" * 80 + "\n")

    async def execute_ai(
        self,
        prompt: str,
        provider: str,
        new_chat: bool = True,
        output_file: str | None = None,
        use_cache: bool = False,
        cache_key_extra: str = "",
    ) -> str:
        """Execute a query against a provider with caching support."""
        cache_key = ""
        self.last_cache_hit = False
        if use_cache:
            cache_raw = cache_key_extra if cache_key_extra else f"{provider}:{prompt}"
            cache_key = hashlib.sha256(cache_raw.encode("utf-8")).hexdigest()
            cached = self._get_cache(cache_key)
            if cached is not None:
                self.last_cache_hit = True
                return cached

        if self.query_executor is None:
            raise RuntimeError("Query executor is not configured on BridgeOrchestrator.")

        raw_response = await self.query_executor(
            prompt=prompt,
            provider_id=provider,
            new_chat=new_chat,
            output_file=output_file,
        )

        if use_cache and cache_key and raw_response:
            check_p = extract_bridge_payload(raw_response)
            if not check_p.truncated:
                self._set_cache(cache_key, raw_response)

        return raw_response

    async def run_stage(
        self,
        task: str,
        provider: str,
        role: str = "general",
        template: str | None = None,
        stage_num: int = 1,
        total_stages: int = 1,
        job_id: str | None = None,
        input_files: list[str] | None = None,
        out_file: str | None = None,
        context_files: list[str] | None = None,
        contract_file: str | None = None,
        verify_cmd: str | None = None,
        max_retries: int = 2,
        use_cache: bool = False,
        new_chat: bool = True,
        cross_review_provider: str | None = None,
        quiet: bool = True,
        print_output: bool = False,
        max_output_lines: int = 20,
    ) -> StageResult:
        """Run a single orchestration stage: build envelope, query AI, handle truncation, verify, patch, log."""
        self.ensure_dirs()
        self.handoff_mgr.auto_sync()

        actual_job_id = job_id or f"job_{secrets.token_hex(4)}"
        actual_role = role or template or "general"
        role_template = self.load_prompt_template(template or actual_role)

        # 1. Gather context
        handoff_content = self.handoff_mgr.read_handoff()
        context_content = build_repo_context(self.project_dir, context_files=context_files)

        # 2. Gather previous stage input
        previous_output = ""
        if input_files:
            input_parts = []
            for inf in input_files:
                inp_path = (self.project_dir / inf).resolve() if not Path(inf).is_absolute() else Path(inf).resolve()
                if inp_path.is_file():
                    try:
                        content = inp_path.read_text(encoding="utf-8", errors="ignore")
                        input_parts.append(f"### {inp_path.name}\n{content}")
                    except Exception as e:
                        input_parts.append(f"### {inp_path.name} (Error reading: {e})")
            previous_output = "\n\n".join(input_parts)

        # 3. Gather contract if present
        contract_content = ""
        if contract_file:
            cp = (self.project_dir / contract_file).resolve() if not Path(contract_file).is_absolute() else Path(contract_file).resolve()
            if cp.is_file():
                contract_content = cp.read_text(encoding="utf-8", errors="ignore")

        # 4. Build prompt envelope
        prompt_envelope = build_prompt_envelope(
            job_id=actual_job_id,
            task=task,
            role=actual_role,
            stage_num=stage_num,
            total_stages=total_stages,
            handoff_content=handoff_content,
            context_content=context_content,
            previous_output=previous_output,
            contract_content=contract_content,
            role_template=role_template,
        )

        self._write_log(actual_job_id, f"STAGE {stage_num}/{total_stages} PROMPT ENVELOPE:\n{prompt_envelope}")

        # 5. Call Provider
        ctx_files_content = ""
        if context_files:
            ctx_files_content = ":".join(
                str((self.project_dir / cf).resolve().read_text(encoding="utf-8", errors="ignore"))
                for cf in context_files
                if (self.project_dir / cf).is_file()
            )
        cache_key_raw = f"{provider}:{actual_role}:{task}:{previous_output}:{contract_content}:{ctx_files_content}"
        raw_response = await self.execute_ai(
            prompt=prompt_envelope,
            provider=provider,
            new_chat=new_chat,
            use_cache=use_cache,
            cache_key_extra=cache_key_raw,
        )
        self._write_log(actual_job_id, f"RAW AI RESPONSE:\n{raw_response}")

        # 6. Extract payload & recover from truncation if needed
        payload = extract_bridge_payload(raw_response)
        if payload.truncated:
            self._write_log(actual_job_id, "TRUNCATION DETECTED. Sending continuation request in same chat.")
            continuation_raw = await self.execute_ai(
                prompt=CONTINUATION_PROMPT,
                provider=provider,
                new_chat=False,
                use_cache=False,
            )
            self._write_log(actual_job_id, f"CONTINUATION RESPONSE:\n{continuation_raw}")
            stitched = stitch_continuation(raw_response, continuation_raw)
            payload = extract_bridge_payload(stitched)
            if use_cache and cache_key_raw:
                c_key = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()
                self._set_cache(c_key, stitched)

        # 7. Apply generated code/files
        files_written = []
        lines_written = 0
        primary_out = out_file or (payload.files[0].filename if payload.files else "")

        if payload.status == "COMPLETE" and payload.files:
            primary_written = False
            for idx, bf in enumerate(payload.files):
                if out_file and not primary_written and (len(payload.files) == 1 or bf.filename == out_file or idx == 0):
                    target_fname = out_file
                    primary_written = True
                else:
                    target_fname = bf.filename or out_file

                if not target_fname:
                    continue
                target_path = (self.project_dir / target_fname).resolve() if not Path(target_fname).is_absolute() else Path(target_fname).resolve()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(bf.content, encoding="utf-8")
                files_written.append(str(target_path.relative_to(self.project_dir) if self.project_dir in target_path.parents else target_path.name))
                lines_written += len(bf.content.splitlines())

                # If model named it differently, also write to original filename
                if target_fname == out_file and bf.filename and bf.filename != out_file:
                    alt_path = (self.project_dir / bf.filename).resolve() if not Path(bf.filename).is_absolute() else Path(bf.filename).resolve()
                    alt_path.parent.mkdir(parents=True, exist_ok=True)
                    alt_path.write_text(bf.content, encoding="utf-8")
        elif payload.status == "COMPLETE" and primary_out and (payload.extracted_text or payload.review_json):
            if payload.review_json and (primary_out.endswith(".json") or actual_role == "reviewer"):
                content_to_write = payload.review_json
            else:
                # Non-file role (or architect contract spec or plain text output)
                clean_body = payload.extracted_text
                clean_body = re.sub(
                    r"^ASSUMPTIONS:\s*.*?(?=^(?:FILE|NEXT|REVIEW_JSON|ANALYSIS|RISKS|NEXT_STEPS):|\Z)",
                    "",
                    clean_body,
                    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
                )
                clean_body = re.sub(
                    r"^NEXT:\s*.*?(?=^(?:FILE|REVIEW_JSON|ANALYSIS|RISKS|NEXT_STEPS):|\Z)",
                    "",
                    clean_body,
                    flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
                )
                clean_body = re.sub(r"^STATUS:\s*.*?\r?\n", "", clean_body, flags=re.MULTILINE | re.IGNORECASE)
                clean_body = re.sub(r"^SUMMARY:\s*.*?\r?\n", "", clean_body, flags=re.MULTILINE | re.IGNORECASE)
                clean_body = re.sub(r"^REVIEW_JSON:\s*", "", clean_body, flags=re.MULTILINE | re.IGNORECASE)
                clean_body = clean_body.strip()
                if clean_body.startswith("```") and clean_body.endswith("```"):
                    clean_body = re.sub(r"^```[a-zA-Z0-9_\-\+]*\r?\n", "", clean_body)
                    clean_body = re.sub(r"\r?\n```$", "", clean_body)
                    clean_body = clean_body.strip()

                if not clean_body and payload.summary:
                    clean_body = payload.summary.strip()

                content_to_write = clean_body if clean_body else payload.extracted_text
            target_path = (self.project_dir / primary_out).resolve() if not Path(primary_out).is_absolute() else Path(primary_out).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content_to_write, encoding="utf-8")
            files_written.append(str(target_path.relative_to(self.project_dir) if self.project_dir in target_path.parents else target_path.name))
            lines_written = len(content_to_write.splitlines())

        # 8. Verification loop
        verify_status = "none"
        verify_error = ""

        if verify_cmd:
            passed, err_log = run_verification(verify_cmd, cwd=self.project_dir)
            if passed:
                verify_status = "PASS"
            else:
                self._write_log(actual_job_id, f"VERIFY FAILED:\n{err_log}")
                # Fixer loop
                attempt = 1
                while attempt <= max_retries and not passed:
                    fixer_prompt = format_fixer_prompt(verify_cmd, err_log, attempt, max_retries)
                    self._write_log(actual_job_id, f"FIXER PROMPT (Attempt {attempt}/{max_retries}):\n{fixer_prompt}")
                    fix_raw = await self.execute_ai(
                        prompt=fixer_prompt,
                        provider=provider,
                        new_chat=False,
                        use_cache=False,
                    )
                    self._write_log(actual_job_id, f"FIXER RAW RESPONSE:\n{fix_raw}")
                    # Apply fix to primary target
                    target_file = (self.project_dir / primary_out).resolve() if primary_out else None
                    if target_file and target_file.exists():
                        apply_patch_or_fallback(target_file, fix_raw)
                        passed, err_log = run_verification(verify_cmd, cwd=self.project_dir)
                        if passed:
                            verify_status = "PASS"
                            self._write_log(actual_job_id, f"VERIFY PASSED AFTER FIXER ATTEMPT {attempt}")
                            break
                    attempt += 1

                if not passed:
                    verify_status = "FAIL"
                    verify_error = err_log

        # 9. Optional Cross-Reviewer Loop
        if verify_status in ("PASS", "none") and cross_review_provider and contract_content and primary_out:
            reviewer_template = self.load_prompt_template("reviewer")
            review_task = f"Verify implementation of {primary_out} strictly against the contract."
            review_envelope = build_prompt_envelope(
                job_id=f"{actual_job_id}_rev",
                task=review_task,
                role="reviewer",
                contract_content=contract_content,
                previous_output=Path(self.project_dir / primary_out).read_text(encoding="utf-8", errors="ignore"),
                role_template=reviewer_template,
            )
            review_raw = await self.execute_ai(
                prompt=review_envelope,
                provider=cross_review_provider,
                new_chat=True,
                use_cache=False,
            )
            self._write_log(actual_job_id, f"CROSS REVIEW ({cross_review_provider}):\n{review_raw}")
            rev_payload = extract_bridge_payload(review_raw)
            if rev_payload.verdict == "FAIL":
                self._write_log(actual_job_id, f"REVIEWER VERDICT FAIL: {rev_payload.extracted_text}")
                # Feed issues back to builder in same chat thread
                builder_fix_prompt = (
                    f"Cross-reviewer found issues with your implementation:\n{rev_payload.extracted_text}\n"
                    "Correct all issues and output the complete updated file."
                )
                fixed_raw = await self.execute_ai(
                    prompt=builder_fix_prompt,
                    provider=provider,
                    new_chat=False,
                    use_cache=False,
                )
                self._write_log(actual_job_id, f"BUILDER FIX FOR REVIEW:\n{fixed_raw}")
                target_file = (self.project_dir / primary_out).resolve() if primary_out else None
                if target_file:
                    apply_patch_or_fallback(target_file, fixed_raw)
                    if verify_cmd:
                        p, err_log = run_verification(verify_cmd, cwd=self.project_dir)
                        verify_status = "PASS" if p else "FAIL"

        # 10. Record to Ledger
        overall_status = payload.status
        if verify_status == "FAIL":
            overall_status = "BLOCKED"

        self.handoff_mgr.record_job(
            job_id=actual_job_id,
            actor=provider,
            role=actual_role,
            action="stage_build",
            files=files_written,
            verify=verify_status,
            status=overall_status,
            summary=payload.summary or f"Completed {actual_role} stage",
            next_step=payload.next_step,
        )

        result = StageResult(
            job_id=actual_job_id,
            stage_num=stage_num,
            total_stages=total_stages,
            provider=provider,
            role=actual_role,
            out_file=primary_out,
            lines_written=lines_written,
            status=overall_status,
            verify=verify_status,
            summary=payload.summary,
            error=verify_error,
            extracted_text=payload.extracted_text,
        )

        # 11. Format Output
        if overall_status == "COMPLETE" and verify_status != "FAIL":
            cache_suffix = " cache=HIT" if getattr(self, "last_cache_hit", False) else ""
            out_line = f"OK job={actual_job_id} stage={stage_num}/{total_stages} out={primary_out} lines={lines_written} status={overall_status} verify={verify_status}{cache_suffix}"
            print(out_line)
        else:
            first_err = verify_error.splitlines()[0] if verify_error else (payload.summary or "Stage execution failed")
            out_line = f"FAIL job={actual_job_id} stage={stage_num}/{total_stages} out={primary_out} status={overall_status} verify={verify_status} error={first_err}"
            print(out_line, file=sys.stderr)
            if verify_error:
                tail = "\n".join(verify_error.splitlines()[-10:])
                print(f"Error details (last 10 lines):\n{tail}", file=sys.stderr)

        if print_output and payload.extracted_text:
            lines = payload.extracted_text.splitlines()
            capped = lines[:max_output_lines]
            print("\n--- Output Preview ---")
            print("\n".join(capped))
            if len(lines) > max_output_lines:
                print(f"... ({len(lines) - max_output_lines} more lines in {primary_out})")
            print("----------------------\n")

        return result

    async def run_pipeline(
        self,
        pipeline_path: str | Path,
        use_cache: bool = False,
        max_retries: int = 2,
        quiet: bool = True,
        print_output: bool = False,
        max_output_lines: int = 20,
    ) -> list[StageResult]:
        """Execute a full multi-stage relay pipeline defined in a YAML or JSON file."""
        p_path = Path(pipeline_path).resolve()
        if not p_path.is_file():
            raise FileNotFoundError(f"Pipeline file not found: {pipeline_path}")

        raw_text = p_path.read_text(encoding="utf-8")
        if p_path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(raw_text)
            except Exception as e:
                raise ValueError(f"Could not parse YAML pipeline: {e}")
        else:
            data = json.loads(raw_text)

        stages = data.get("stages", [])
        if not stages:
            raise ValueError("Pipeline file contains no 'stages' definitions.")

        total_stages = len(stages)
        results: list[StageResult] = []
        contract_file = None

        for idx, stage in enumerate(stages, 1):
            provider = stage.get("provider", "gemini")
            template = stage.get("template")
            role = stage.get("role", template or "general")
            task = stage.get("task", f"Execute stage {idx}: {role}")
            if "task_file" in stage:
                tf = (self.project_dir / stage["task_file"]).resolve()
                if tf.is_file():
                    task = tf.read_text(encoding="utf-8", errors="ignore").strip()

            out_file = stage.get("out")
            in_spec = stage.get("in", [])
            in_files = [in_spec] if isinstance(in_spec, str) else list(in_spec)

            # Stage 1 defines contract if template is architect or if marked
            if idx == 1 and (template == "architect" or role == "architect"):
                contract_file = out_file

            res = await self.run_stage(
                task=task,
                provider=provider,
                role=role,
                template=template,
                stage_num=idx,
                total_stages=total_stages,
                input_files=in_files,
                out_file=out_file,
                context_files=stage.get("context_files"),
                contract_file=stage.get("contract", contract_file),
                verify_cmd=stage.get("verify"),
                max_retries=stage.get("max_retries", max_retries),
                use_cache=stage.get("cache", use_cache),
                cross_review_provider=stage.get("review_provider"),
                quiet=quiet,
                print_output=print_output,
                max_output_lines=max_output_lines,
            )
            results.append(res)
            if res.status != "COMPLETE" or res.verify == "FAIL":
                print(f"Pipeline halted at stage {idx}/{total_stages} due to failure.", file=sys.stderr)
                break

        return results

    async def handoff_command(
        self,
        to_provider: str,
        goal: str | None = None,
        use_cache: bool = False,
        print_output: bool = False,
        max_output_lines: int = 20,
    ) -> str:
        """Run the analyst role across HANDOFF + repo map + last diff, append to ledger, and print one line."""
        self.ensure_dirs()
        self.handoff_mgr.auto_sync()
        if goal:
            self.handoff_mgr.regenerate_handoff(goal=goal)

        handoff_content = self.handoff_mgr.read_handoff()
        repo_map = build_repo_map(self.project_dir)
        git_state = self.handoff_mgr.get_git_state()

        context_content = f"{repo_map}\n\n### Working Tree / Diff Status\n{git_state['stat']}"
        analyst_template = self.load_prompt_template("analyst")

        task = (
            "Analyze current project state, recent changes (especially manual user edits), "
            "and active code files to recommend next actions."
        )
        if goal:
            task += f" Goal: {goal}"

        job_id = f"handoff_{secrets.token_hex(3)}"
        prompt_envelope = build_prompt_envelope(
            job_id=job_id,
            task=task,
            role="analyst",
            stage_num=1,
            total_stages=1,
            handoff_content=handoff_content,
            context_content=context_content,
            role_template=analyst_template,
        )

        self._write_log(job_id, f"HANDOFF ANALYST PROMPT:\n{prompt_envelope}")

        raw_response = await self.execute_ai(
            prompt=prompt_envelope,
            provider=to_provider,
            new_chat=False,
            use_cache=use_cache,
            cache_key_extra=f"handoff_{git_state['hash']}",
        )
        self._write_log(job_id, f"HANDOFF RAW RESPONSE:\n{raw_response}")

        payload = extract_bridge_payload(raw_response)
        summary_text = payload.summary or "Handoff analysis completed"

        # Record to ledger
        self.handoff_mgr.record_job(
            job_id=job_id,
            actor=to_provider,
            role="analyst",
            action="handoff",
            files=[],
            verify="none",
            status=payload.status,
            summary=summary_text,
            next_step=payload.next_step or payload.next_steps,
        )

        one_line = f"OK handoff to={to_provider} status={payload.status} checkpoint={git_state['hash']}"
        print(one_line)

        if print_output:
            print("\n--- Analyst Handoff Output ---")
            lines = (payload.extracted_text or raw_response).splitlines()
            print("\n".join(lines[:max_output_lines]))
            print("------------------------------\n")

        return one_line

    async def council_command(
        self,
        task: str,
        providers: list[str],
        synthesizer_provider: str,
        output_file: str | None = None,
        print_output: bool = False,
    ) -> str:
        """Execute Round 1 independent queries followed by Round 2 anonymous synthesis."""
        self.ensure_dirs()
        job_id = f"council_{secrets.token_hex(3)}"

        # Round 1: Independent
        r1_prompt = build_council_round1_prompt(task)
        candidate_outputs: list[str] = []

        for p in providers:
            raw = await self.execute_ai(prompt=r1_prompt, provider=p, new_chat=False)
            candidate_outputs.append(raw.strip())
            self._write_log(job_id, f"ROUND 1 ({p}):\n{raw}")

        labels = list(string.ascii_uppercase)
        council_dir = self.project_dir / ".bridge" / "council"
        council_dir.mkdir(parents=True, exist_ok=True)
        for i, (p, raw) in enumerate(zip(providers, candidate_outputs)):
            lbl = labels[i] if i < len(labels) else str(i + 1)
            (council_dir / f"{job_id}_candidate_{lbl}.md").write_text(raw, encoding="utf-8")
            if output_file:
                out_base = Path(output_file).stem
                out_ext = Path(output_file).suffix
                cand_file = self.project_dir / f"{out_base}_candidate_{lbl}{out_ext}"
                cand_file.write_text(raw, encoding="utf-8")

        # Round 2: Synthesis
        r2_prompt = build_council_round2_prompt(task, candidate_outputs)
        synthesizer = synthesizer_provider or providers[0]
        self._write_log(job_id, f"ROUND 2 SYNTHESIS PROMPT ({synthesizer}):\n{r2_prompt}")
        synth_raw = await self.execute_ai(prompt=r2_prompt, provider=synthesizer, new_chat=False)
        self._write_log(job_id, f"ROUND 2 SYNTHESIS RESPONSE ({synthesizer}):\n{synth_raw}")

        if output_file:
            out_p = (self.project_dir / output_file).resolve() if not Path(output_file).is_absolute() else Path(output_file).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            candidate_sections = []
            for i, raw in enumerate(candidate_outputs):
                lbl = labels[i] if i < len(labels) else str(i + 1)
                candidate_sections.append(f"### Candidate {lbl}\n{raw}")
            combined_md = f"# Council Synthesis\n\n{synth_raw}\n\n---\n## Candidate Proposals\n\n" + "\n\n".join(candidate_sections)
            out_p.write_text(combined_md, encoding="utf-8")

        self.handoff_mgr.record_job(
            job_id=job_id,
            actor=synthesizer,
            role="synthesizer",
            action="council",
            files=[output_file] if output_file else [],
            verify="none",
            status="COMPLETE",
            summary=f"Council synthesis across {','.join(providers)}",
            next_step="Review council decision in " + (output_file or "log"),
        )

        summary_line = f"OK council providers={','.join(providers)} synthesizer={synthesizer} status=COMPLETE"
        print(summary_line)

        if print_output:
            print("\n--- Council Synthesis ---")
            print(synth_raw)
            print("-------------------------\n")

        return synth_raw
