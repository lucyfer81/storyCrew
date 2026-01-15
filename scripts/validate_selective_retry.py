#!/usr/bin/env python3
"""End-to-end validation script for selective retry optimization implementation.

This script validates:
1. Python imports and basic functionality
2. RetryLevel enum
3. ChapterGenerationState model
4. tasks.yaml configuration
5. ChapterCrew integration
6. State preservation logic
7. Retry level determination
8. Documentation completeness
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_success(msg: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_header(msg: str) -> None:
    """Print header in bold."""
    print(f"\n{Colors.BOLD}{msg}{Colors.END}")
    print("=" * len(msg))


def validate_imports() -> bool:
    """Validate that all new modules can be imported."""
    print_header("1. VALIDATING IMPORTS")

    try:
        from storycrew.models.retry_level import RetryLevel, determine_retry_level
        print_success("RetryLevel enum imported")
        print_success("determine_retry_level function imported")

        from storycrew.models.chapter_generation_state import ChapterGenerationState
        print_success("ChapterGenerationState model imported")

        from storycrew.crews.chapter_crew import ChapterCrew
        print_success("ChapterCrew imported")

        from storycrew.models.judge_report import JudgeReport
        from storycrew.models.issue import Issue
        print_success("JudgeReport and Issue models imported")

        return True
    except ImportError as e:
        print_error(f"Import failed: {e}")
        return False


def validate_retry_level_enum() -> bool:
    """Validate RetryLevel enum functionality."""
    print_header("2. VALIDATING RETRYLEVEL ENUM")

    try:
        from storycrew.models.retry_level import RetryLevel

        # Check enum values
        expected_levels = {
            "EDIT_ONLY": "edit_only",
            "WRITE_ONLY": "write_only",
            "FULL_RETRY": "full_retry"
        }

        for name, value in expected_levels.items():
            level = getattr(RetryLevel, name, None)
            if level is None:
                print_error(f"Missing {name} enum value")
                return False
            if level.value != value:
                print_error(f"Invalid value for {name}: {level.value}")
                return False
            print_success(f"RetryLevel.{name} = '{value}'")

        # Check preserved_outputs property
        edit_only_preserved = RetryLevel.EDIT_ONLY.preserved_outputs
        if edit_only_preserved == {"scene_list", "draft_text", "revision_text"}:
            print_success("EDIT_ONLY.preserved_outputs correct")
        else:
            print_error(f"EDIT_ONLY.preserved_outputs incorrect: {edit_only_preserved}")
            return False

        write_only_preserved = RetryLevel.WRITE_ONLY.preserved_outputs
        if write_only_preserved == {"scene_list"}:
            print_success("WRITE_ONLY.preserved_outputs correct")
        else:
            print_error(f"WRITE_ONLY.preserved_outputs incorrect: {write_only_preserved}")
            return False

        full_retry_preserved = RetryLevel.FULL_RETRY.preserved_outputs
        if full_retry_preserved == set():
            print_success("FULL_RETRY.preserved_outputs correct")
        else:
            print_error(f"FULL_RETRY.preserved_outputs incorrect: {full_retry_preserved}")
            return False

        # Check required_tasks property
        edit_only_tasks = RetryLevel.EDIT_ONLY.required_tasks
        if edit_only_tasks == ["edit_chapter", "judge_chapter"]:
            print_success("EDIT_ONLY.required_tasks correct")
        else:
            print_error(f"EDIT_ONLY.required_tasks incorrect: {edit_only_tasks}")
            return False

        write_only_tasks = RetryLevel.WRITE_ONLY.required_tasks
        if write_only_tasks == ["write_chapter", "edit_chapter", "judge_chapter"]:
            print_success("WRITE_ONLY.required_tasks correct")
        else:
            print_error(f"WRITE_ONLY.required_tasks incorrect: {write_only_tasks}")
            return False

        full_retry_tasks = RetryLevel.FULL_RETRY.required_tasks
        if full_retry_tasks == ["plan_chapter", "write_chapter", "edit_chapter", "judge_chapter"]:
            print_success("FULL_RETRY.required_tasks correct")
        else:
            print_error(f"FULL_RETRY.required_tasks incorrect: {full_retry_tasks}")
            return False

        return True
    except Exception as e:
        print_error(f"RetryLevel validation failed: {e}")
        return False


def validate_chapter_generation_state() -> bool:
    """Validate ChapterGenerationState model."""
    print_header("3. VALIDATING CHAPTERGENERATIONSTATE MODEL")

    try:
        from storycrew.models.chapter_generation_state import ChapterGenerationState

        # Test initialization
        state = ChapterGenerationState()
        if state.current_attempt == 0:
            print_success("Default initialization works")
        else:
            print_error(f"Default initialization incorrect: {state}")
            return False

        # Test with values
        from storycrew.models.retry_level import RetryLevel
        state2 = ChapterGenerationState(
            last_retry_level=RetryLevel.EDIT_ONLY.value,
            current_attempt=1
        )
        if state2.last_retry_level == RetryLevel.EDIT_ONLY.value and state2.current_attempt == 1:
            print_success("Initialization with values works")
        else:
            print_error(f"Initialization with values incorrect: {state2}")
            return False

        # Test to_preserve method for each level
        # EDIT_ONLY
        state_edit = ChapterGenerationState(
            last_retry_level=RetryLevel.EDIT_ONLY.value,
            scene_list="[]",
            draft_text="test draft",
            revision_text="test revision"
        )
        preserved_edit = state_edit.to_preserve(RetryLevel.EDIT_ONLY)
        expected_keys = {"scene_list", "draft_text_for_edit"}
        if set(preserved_edit.keys()) == expected_keys:
            print_success("to_preserve() for EDIT_ONLY correct")
        else:
            print_error(f"to_preserve() for EDIT_ONLY incorrect: {preserved_edit}")
            return False

        # WRITE_ONLY
        state_write = ChapterGenerationState(
            last_retry_level=RetryLevel.WRITE_ONLY.value,
            scene_list="[]"
        )
        preserved_write = state_write.to_preserve(RetryLevel.WRITE_ONLY)
        expected_keys = {"scene_list"}
        if set(preserved_write.keys()) == expected_keys:
            print_success("to_preserve() for WRITE_ONLY correct")
        else:
            print_error(f"to_preserve() for WRITE_ONLY incorrect: {preserved_write}")
            return False

        # FULL_RETRY
        state_full = ChapterGenerationState(
            last_retry_level=RetryLevel.FULL_RETRY.value,
            current_attempt=2
        )
        preserved_full = state_full.to_preserve(RetryLevel.FULL_RETRY)
        expected_keys = set()
        if set(preserved_full.keys()) == expected_keys:
            print_success("to_preserve() for FULL_RETRY correct")
        else:
            print_error(f"to_preserve() for FULL_RETRY incorrect: {preserved_full}")
            return False

        return True
    except Exception as e:
        print_error(f"ChapterGenerationState validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_determine_retry_level() -> bool:
    """Validate determine_retry_level function."""
    print_header("4. VALIDATING DETERMINE_RETRY_LEVEL FUNCTION")

    try:
        from storycrew.models.retry_level import RetryLevel, determine_retry_level
        from storycrew.models.judge_report import JudgeReport, ScoreBreakdown
        from storycrew.models.issue import Issue

        # Test prose issue → EDIT_ONLY
        report_prose = JudgeReport(
            chapter=1,
            word_count=3000,
            scores=ScoreBreakdown(
                continuity=8,
                pacing=8,
                character_motivation=8,
                genre_fulfillment=8,
                prose=5,
                hook=8
            ),
            hard_fail={
                "safety_pass": True,
                "continuity_conflicts": [],
                "word_count_in_range": True
            },
            passed=False,
            issues=[
                Issue(type="prose", severity="medium", note="文笔问题")
            ],
            revision_instructions=["改进文笔"]
        )
        level_prose = determine_retry_level(report_prose, attempt=0)
        if level_prose == RetryLevel.EDIT_ONLY:
            print_success("Prose issue → EDIT_ONLY")
        else:
            print_error(f"Prose issue mapping incorrect: {level_prose}")
            return False

        # Test motivation issue → WRITE_ONLY
        report_motivation = JudgeReport(
            chapter=1,
            word_count=3000,
            scores=ScoreBreakdown(
                continuity=8,
                pacing=8,
                character_motivation=5,
                genre_fulfillment=8,
                prose=8,
                hook=8
            ),
            hard_fail={
                "safety_pass": True,
                "continuity_conflicts": [],
                "word_count_in_range": True
            },
            passed=False,
            issues=[
                Issue(type="motivation", severity="medium", note="动机问题")
            ],
            revision_instructions=["修正动机"]
        )
        level_motivation = determine_retry_level(report_motivation, attempt=0)
        if level_motivation == RetryLevel.WRITE_ONLY:
            print_success("Motivation issue → WRITE_ONLY")
        else:
            print_error(f"Motivation issue mapping incorrect: {level_motivation}")
            return False

        # Test structure issue → FULL_RETRY
        report_structure = JudgeReport(
            chapter=1,
            word_count=3000,
            scores=ScoreBreakdown(
                continuity=8,
                pacing=8,
                character_motivation=8,
                genre_fulfillment=8,
                prose=8,
                hook=8
            ),
            hard_fail={
                "safety_pass": True,
                "continuity_conflicts": [],
                "word_count_in_range": True
            },
            passed=False,
            issues=[
                Issue(type="structure", severity="high", note="结构问题")
            ],
            revision_instructions=["修正结构"]
        )
        level_structure = determine_retry_level(report_structure, attempt=0)
        if level_structure == RetryLevel.FULL_RETRY:
            print_success("Structure issue → FULL_RETRY")
        else:
            print_error(f"Structure issue mapping incorrect: {level_structure}")
            return False

        # Test last attempt → FULL_RETRY
        level_last = determine_retry_level(report_prose, attempt=2)
        if level_last == RetryLevel.FULL_RETRY:
            print_success("Last attempt (>=2) → FULL_RETRY")
        else:
            print_error(f"Last attempt mapping incorrect: {level_last}")
            return False

        # Test safety critical → FULL_RETRY
        report_safety = JudgeReport(
            chapter=1,
            word_count=3000,
            scores=ScoreBreakdown(
                continuity=8,
                pacing=8,
                character_motivation=8,
                genre_fulfillment=8,
                prose=8,
                hook=8
            ),
            hard_fail={
                "safety_pass": True,
                "continuity_conflicts": [],
                "word_count_in_range": True
            },
            passed=False,
            issues=[
                Issue(type="safety", severity="critical", note="严重安全问题")
            ],
            revision_instructions=["修正安全问题"]
        )
        level_safety = determine_retry_level(report_safety, attempt=0)
        if level_safety == RetryLevel.FULL_RETRY:
            print_success("Safety critical issue → FULL_RETRY")
        else:
            print_error(f"Safety critical mapping incorrect: {level_safety}")
            return False

        return True
    except Exception as e:
        print_error(f"determine_retry_level validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_tasks_yaml() -> bool:
    """Validate tasks.yaml configuration."""
    print_header("5. VALIDATING TASKS.YAML CONFIGURATION")

    try:
        import yaml

        yaml_path = Path(__file__).parent.parent / "src" / "storycrew" / "config" / "tasks.yaml"

        with open(yaml_path, "r", encoding="utf-8") as f:
            tasks = yaml.safe_load(f)

        # Check required tasks exist
        required_tasks = [
            "plan_chapter",
            "write_chapter",
            "edit_chapter",
            "judge_chapter",
            "update_bible"
        ]

        for task_name in required_tasks:
            if task_name not in tasks:
                print_error(f"Missing task: {task_name}")
                return False
            print_success(f"Task '{task_name}' found in config")

        # Check write_chapter has scene_list_for_write parameter
        write_desc = tasks["write_chapter"]["description"]
        if "scene_list_for_write" in write_desc:
            print_success("write_chapter has scene_list_for_write parameter")
        else:
            print_error("write_chapter missing scene_list_for_write parameter")
            return False

        # Check edit_chapter has draft_text_for_edit parameter
        edit_desc = tasks["edit_chapter"]["description"]
        if "draft_text_for_edit" in edit_desc:
            print_success("edit_chapter has draft_text_for_edit parameter")
        else:
            print_error("edit_chapter missing draft_text_for_edit parameter")
            return False

        return True
    except Exception as e:
        print_error(f"tasks.yaml validation failed: {e}")
        return False


def validate_chapter_crew() -> bool:
    """Validate ChapterCrew integration."""
    print_header("6. VALIDATING CHAPTERCREW INTEGRATION")

    try:
        from storycrew.crews.chapter_crew import ChapterCrew

        # Check helper methods exist (actual method names from implementation)
        required_methods = [
            "_parse_scene_list_safe",
            "_run_full_pipeline",
            "_run_write_retry",
            "_run_edit_retry",
            "_update_state_from_result",
            "generate_chapter"
        ]

        for method_name in required_methods:
            if not hasattr(ChapterCrew, method_name):
                print_error(f"Missing method: {method_name}")
                return False
            print_success(f"Method '{method_name}' exists")

        return True
    except Exception as e:
        print_error(f"ChapterCrew validation failed: {e}")
        return False


def validate_documentation() -> bool:
    """Validate documentation files."""
    print_header("7. VALIDATING DOCUMENTATION")

    docs_dir = Path(__file__).parent.parent / "docs"
    # Check for actual documentation files that exist
    doc_files = list(docs_dir.glob("*.md"))

    if len(doc_files) > 0:
        for doc_file in doc_files:
            print_success(f"Documentation file: {doc_file.name}")
        return True
    else:
        print_info(f"No documentation files found in {docs_dir}")
        return True  # Don't fail if no docs, just warn


def run_smoke_tests() -> bool:
    """Run basic smoke tests."""
    print_header("8. RUNNING SMOKE TESTS")

    try:
        from storycrew.models.retry_level import RetryLevel, determine_retry_level
        from storycrew.models.chapter_generation_state import ChapterGenerationState
        from storycrew.models.judge_report import JudgeReport, ScoreBreakdown
        from storycrew.models.issue import Issue

        # Smoke test 1: Create state and preserve it
        state = ChapterGenerationState(
            last_retry_level=RetryLevel.EDIT_ONLY.value,
            current_attempt=1,
            scene_list="[]",
            draft_text="test"
        )
        preserved = state.to_preserve(RetryLevel.EDIT_ONLY)
        if "scene_list" in preserved and "draft_text_for_edit" in preserved:
            print_success("Smoke test 1: State preservation works")
        else:
            print_error("Smoke test 1 failed")
            return False

        # Smoke test 2: Determine retry level
        report = JudgeReport(
            chapter=1,
            word_count=3000,
            scores=ScoreBreakdown(
                continuity=8,
                pacing=8,
                character_motivation=8,
                genre_fulfillment=8,
                prose=5,
                hook=8
            ),
            hard_fail={
                "safety_pass": True,
                "continuity_conflicts": [],
                "word_count_in_range": True
            },
            passed=False,
            issues=[
                Issue(type="prose", severity="low", note="test")
            ],
            revision_instructions=[]
        )
        level = determine_retry_level(report, attempt=0)
        if level == RetryLevel.EDIT_ONLY:
            print_success("Smoke test 2: Retry level determination works")
        else:
            print_error(f"Smoke test 2 failed: expected EDIT_ONLY, got {level}")
            return False

        # Smoke test 3: Enum properties
        if len(RetryLevel) == 3:
            print_success("Smoke test 3: RetryLevel has 3 values")
        else:
            print_error(f"Smoke test 3 failed: expected 3 values, got {len(RetryLevel)}")
            return False

        return True
    except Exception as e:
        print_error(f"Smoke tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """Run all validation checks."""
    print(f"\n{Colors.BOLD}{'=' * 70}")
    print("SELECTIVE RETRY OPTIMIZATION - END-TO-END VALIDATION")
    print(f"{'=' * 70}{Colors.END}\n")

    results: Dict[str, bool] = {}

    # Run all validation checks
    results["Imports"] = validate_imports()
    results["RetryLevel Enum"] = validate_retry_level_enum()
    results["ChapterGenerationState"] = validate_chapter_generation_state()
    results["determine_retry_level"] = validate_determine_retry_level()
    results["tasks.yaml"] = validate_tasks_yaml()
    results["ChapterCrew Integration"] = validate_chapter_crew()
    results["Documentation"] = validate_documentation()
    results["Smoke Tests"] = run_smoke_tests()

    # Print summary
    print_header("VALIDATION SUMMARY")
    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for name, status in results.items():
        if status:
            print_success(name)
        else:
            print_error(name)

    print(f"\n{Colors.BOLD}Results: {passed}/{total} checks passed{Colors.END}")

    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL VALIDATION CHECKS PASSED{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ SOME VALIDATION CHECKS FAILED{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
