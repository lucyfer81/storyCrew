#!/usr/bin/env python
"""
StoryCrew - Novel Generation System

A CrewAI-based system for generating 9-chapter novels with romance or mystery genres.
Features quality gates, continuity tracking, and automated chapter generation.
"""
import sys
import warnings
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from storycrew.crews import InitCrew, ChapterCrew, FinalCrew
from crewai import Process

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def setup_logging() -> logging.Logger:
    """
    Set up logging configuration for the current run.

    Creates a logs directory if it doesn't exist and sets up a new log file
    with timestamp for each run.

    Returns:
        Configured logger instance
    """
    # Create logs directory
    logs_dir = Path("./logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"story_generation_{timestamp}.log"

    # Configure logging
    logger = logging.getLogger("StoryCrew")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Log initialization
    logger.info("=" * 80)
    logger.info("StoryCrew Logging Initialized")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)

    return logger


def run(
    genre: str = "romance",
    theme_statement: str = "一个关于职场爱情的故事",
    additional_preferences: str = "",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the complete story generation pipeline.

    Args:
        genre: "romance" or "mystery"
        theme_statement: Core theme of the story
        additional_preferences: Optional user preferences
        output_dir: Directory to save output files (default: ./output)

    Returns:
        Dictionary containing generation results and metadata
    """
    # Setup logging
    logger = setup_logging()

    logger.info("Starting StoryCrew Novel Generation")
    logger.info(f"Genre: {genre}")
    logger.info(f"Theme: {theme_statement}")
    logger.info(f"Additional Preferences: {additional_preferences if additional_preferences else 'None'}")

    print("=" * 80)
    print("StoryCrew: Novel Generation System")
    print("=" * 80)
    print(f"Genre: {genre}")
    print(f"Theme: {theme_statement}")
    print()

    # Setup base output directory
    if output_dir is None:
        base_output_dir = Path("./novels")
    else:
        base_output_dir = Path(output_dir)
    base_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {base_output_dir.absolute()}")

    # Track generation metadata
    generation_metadata = {
        "genre": genre,
        "theme_statement": theme_statement,
        "additional_preferences": additional_preferences,
        "start_time": datetime.now().isoformat(),
        "chapters_generated": [],
        "total_chapters": 9,
        "novel_name": None,  # Will be set after initialization
        "novel_dir": None
    }

    # ==================== PHASE 1: INITIALIZATION ====================
    logger.info("=" * 80)
    logger.info("[Phase 1] Initialization - Creating novel name, StorySpec, StoryBible, and Outline")
    logger.info("=" * 80)

    print("[Phase 1] Initialization - Creating novel name, StorySpec, StoryBible, and Outline")
    print("-" * 80)

    init_crew = InitCrew()
    init_inputs = {
        "genre": genre,
        "theme_statement": theme_statement,
        "additional_preferences": additional_preferences
    }

    try:
        logger.info("Starting InitCrew kickoff...")
        init_result = init_crew.kickoff(inputs=init_inputs)
        logger.info("InitCrew completed successfully")
        print("✓ Initialization complete")
        print()

        # Parse novel_name and story_spec from init_result
        # The result is a dict with Pydantic objects
        try:
            # Convert Pydantic objects to dicts for JSON serialization
            def pydantic_to_dict(obj):
                """Convert Pydantic objects to dictionaries."""
                if hasattr(obj, 'model_dump'):
                    return obj.model_dump()
                elif hasattr(obj, 'dict'):
                    return obj.dict()
                elif isinstance(obj, dict):
                    return {k: pydantic_to_dict(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [pydantic_to_dict(item) for item in obj]
                else:
                    return obj

            # Convert result dict to JSON-serializable format
            result_dict = {k: pydantic_to_dict(v) for k, v in init_result.items()}

            # Extract novel_name (it's already at top level now)
            novel_name = result_dict.get('novel_name', '未命名小说')
            story_spec = result_dict.get('story_spec', {})
            story_bible = result_dict.get('story_bible', {})
            outline = result_dict.get('outline', {})

            # Sanitize novel name for directory (remove special characters)
            novel_name_sanitized = re.sub(r'[<>:"/\\|?*]', '', novel_name)
            novel_name_sanitized = novel_name_sanitized.strip()

            logger.info(f"Novel Name extracted: {novel_name}")
            logger.info(f"Sanitized directory name: {novel_name_sanitized}")

            print(f"✓ Novel Name: {novel_name}")
            print()

            # Create novel-specific directory
            novel_dir = base_output_dir / novel_name_sanitized
            novel_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Created novel directory: {novel_dir.absolute()}")
            print(f"✓ Created novel directory: {novel_dir}")
            print()

            # Update metadata
            generation_metadata['novel_name'] = novel_name
            generation_metadata['novel_dir'] = str(novel_dir.absolute())

        except (json.JSONDecodeError, TypeError) as e:
            print(f"⚠ Warning: Could not parse novel_name from result: {e}")
            print("Using default naming...")
            novel_name = f"{genre}_novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            novel_dir = base_output_dir / novel_name
            novel_dir.mkdir(parents=True, exist_ok=True)

            story_spec = init_inputs
            story_bible = init_inputs
            outline = init_inputs

            generation_metadata['novel_name'] = novel_name
            generation_metadata['novel_dir'] = str(novel_dir.absolute())

        # Save initialization outputs to novel directory
        with open(novel_dir / "story_spec.json", "w", encoding="utf-8") as f:
            json.dump(story_spec, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved StorySpec to {novel_dir / 'story_spec.json'}")

        with open(novel_dir / "story_bible.json", "w", encoding="utf-8") as f:
            json.dump(story_bible, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved StoryBible to {novel_dir / 'story_bible.json'}")

        with open(novel_dir / "outline.json", "w", encoding="utf-8") as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved Outline to {novel_dir / 'outline.json'}")
        print()

    except Exception as e:
        logger.error(f"Initialization failed: {e}", exc_info=True)
        print(f"✗ Initialization failed: {e}")
        raise

    # ==================== PHASE 2: CHAPTER GENERATION LOOP ====================
    logger.info("=" * 80)
    logger.info("[Phase 2] Chapter Generation - Writing 9 chapters with quality gates")
    logger.info("=" * 80)

    print("[Phase 2] Chapter Generation - Writing 9 chapters with quality gates")
    print("-" * 80)

    chapter_crew = ChapterCrew()
    chapters = []
    current_bible = story_bible

    for chapter_num in range(1, 10):
        logger.info(f"[Chapter {chapter_num}/9] Starting generation...")
        print(f"[Chapter {chapter_num}/9] Starting generation...")

        # Extract chapter outline from BookOutline
        if isinstance(outline, dict) and 'chapters' in outline:
            outline_list = outline.get('chapters', [])
            if outline_list and len(outline_list) >= chapter_num:
                chapter_outline = outline_list[chapter_num - 1]
            else:
                chapter_outline = {}
        else:
            chapter_outline = {}

        try:
            result = chapter_crew.generate_chapter(
                chapter_number=chapter_num,
                chapter_outline=chapter_outline,
                story_bible=current_bible,
                story_spec=story_spec
            )

            chapter_text = result.get('chapter_text', '')
            updated_bible = result.get('updated_bible', current_bible)
            judge_report = result.get('judge_report', {})
            attempts = result.get('attempts', 1)

            # Convert Pydantic objects to dicts if needed
            if hasattr(updated_bible, 'model_dump'):
                updated_bible = updated_bible.model_dump()
            if hasattr(judge_report, 'model_dump'):
                judge_report = judge_report.model_dump()

            # Validate chapter_text before saving
            if not chapter_text or (isinstance(chapter_text, str) and chapter_text.strip() == ''):
                logger.warning(f"Chapter {chapter_num} text is empty or invalid!")
                logger.warning(f"Attempt: {attempts}")
                logger.warning(f"Result keys: {list(result.keys())}")
                logger.warning(f"chapter_text type: {type(chapter_text)}")
                print(f"⚠ Warning: Chapter {chapter_num} text is empty or invalid!")
                print(f"  Attempt: {attempts}")
                print(f"  Result keys: {list(result.keys())}")
                print(f"  chapter_text type: {type(chapter_text)}")
                # Try to extract from raw result if available
                if 'raw_result' in result:
                    logger.info("Attempting to extract from raw_result...")
                    print(f"  Attempting to extract from raw_result...")
                    chapter_text = str(result.get('raw_result', ''))
                # New: if chapter_text is a dict, try to extract raw_output field
                elif isinstance(chapter_text, dict) and 'raw_output' in chapter_text:
                    logger.info("Extracting from raw_output field in dictionary...")
                    print(f"  Extracting from raw_output field in dictionary...")
                    chapter_text = chapter_text.get('raw_output', '')
                # Continue anyway - file will be empty but won't crash
            else:
                # New: check if chapter_text is a dictionary
                if isinstance(chapter_text, dict):
                    if 'raw_output' in chapter_text:
                        logger.warning(f"Chapter {chapter_num} text is a dictionary, extracting raw_output...")
                        print(f"  ⚠ Warning: chapter_text is a dict, extracting raw_output...")
                        chapter_text = chapter_text.get('raw_output', '')
                    else:
                        logger.warning(f"Chapter {chapter_num} text is an unexpected dictionary!")
                        print(f"  ⚠ Warning: chapter_text is an unexpected dict: {list(chapter_text.keys())}")
                        chapter_text = str(chapter_text)

                # Log chapter text length for verification
                text_length = len(chapter_text) if isinstance(chapter_text, str) else 0
                logger.info(f"Chapter {chapter_num} text length: {text_length} characters")
                print(f"  Chapter text length: {text_length} characters")

            # Check if chapter passed quality gate
            if judge_report.get('passed', False):
                logger.info(f"Chapter {chapter_num} completed successfully (attempts: {attempts})")
                print(f"✓ Chapter {chapter_num} complete (attempts: {attempts})")
                chapters.append(chapter_text)
                current_bible = updated_bible

                # Save chapter
                chapter_file = novel_dir / f"chapter_{chapter_num:02d}.md"
                with open(chapter_file, "w", encoding="utf-8") as f:
                    f.write(chapter_text)
                logger.info(f"Saved chapter {chapter_num} to {chapter_file}")
                print(f"✓ Saved chapter {chapter_num} to {chapter_file}")
            else:
                logger.warning(f"Chapter {chapter_num} did not pass quality gate after {attempts} attempts")
                logger.warning(f"Issues: {[issue.get('note') for issue in judge_report.get('issues', [])]}")
                print(f"⚠ Chapter {chapter_num} did not pass quality gate after {attempts} attempts")
                print(f"  Issues: {[issue.get('note') for issue in judge_report.get('issues', [])]}")
                # Still save and continue (can be manually fixed later)
                chapters.append(chapter_text)
                current_bible = updated_bible

                chapter_file = novel_dir / f"chapter_{chapter_num:02d}_needs_review.md"
                with open(chapter_file, "w", encoding="utf-8") as f:
                    f.write(chapter_text)
                logger.info(f"Saved chapter {chapter_num} (needs review) to {chapter_file}")
                print(f"✓ Saved chapter {chapter_num} (needs review) to {chapter_file}")

            # Track metadata
            generation_metadata['chapters_generated'].append({
                "chapter": chapter_num,
                "attempts": attempts,
                "passed": judge_report.get('passed', False),
                "scores": judge_report.get('scores', {})
            })

        except Exception as e:
            logger.error(f"Chapter {chapter_num} failed: {e}", exc_info=True)
            print(f"✗ Chapter {chapter_num} failed: {e}")
            print("  Continuing with next chapter...")
            continue

        print()

    # Save updated StoryBible
    logger.info("Saving final StoryBible...")
    with open(novel_dir / "story_bible_final.json", "w", encoding="utf-8") as f:
        json.dump(current_bible, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved final StoryBible to {novel_dir / 'story_bible_final.json'}")
    print(f"✓ Saved final StoryBible to {novel_dir / 'story_bible_final.json'}")
    print()

    # ==================== PHASE 3: FINAL ASSEMBLY ====================
    logger.info("=" * 80)
    logger.info("[Phase 3] Final Assembly - Generate metadata and assemble novel")
    logger.info("=" * 80)

    print("[Phase 3] Final Assembly - Generate metadata and assemble novel")
    print("-" * 80)

    # Step 1: Generate metadata using LLM (title, introduction, TOC)
    logger.info("Step 1: Generating novel metadata (title, introduction, TOC)...")
    print("Step 1: Generating novel metadata...")

    try:
        from storycrew.crew import Storycrew
        base_crew = Storycrew()

        # Extract chapter titles for metadata generation
        chapter_titles = []
        for i in range(1, 10):
            chapter_file = novel_dir / f"chapter_{i:02d}.md"
            if chapter_file.exists():
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line:
                        chapter_titles.append(first_line)
                    else:
                        chapter_titles.append(f"第{i}章")
            else:
                chapter_titles.append(f"第{i}章")

        # Create metadata generation task
        metadata_task = base_crew.generate_novel_metadata()
        metadata_task.agent = base_crew.line_editor()

        # Prepare inputs
        metadata_inputs = {
            "story_spec": story_spec.model_dump() if hasattr(story_spec, 'model_dump') else story_spec,
            "story_bible": current_bible.model_dump() if hasattr(current_bible, 'model_dump') else current_bible,
            "chapter_titles": chapter_titles
        }

        # Execute metadata generation
        from crewai import Crew
        metadata_crew = Crew(
            agents=[base_crew.line_editor()],
            tasks=[metadata_task],
            process=Process.sequential,
            verbose=True
        )

        metadata_result = metadata_crew.kickoff(inputs=metadata_inputs)
        metadata = metadata_result.pydantic  # NovelMetadata object

        logger.info(f"Generated metadata:")
        logger.info(f"  Title: {metadata.title}")
        logger.info(f"  Introduction: {metadata.introduction[:100]}...")
        logger.info(f"  TOC: {len(metadata.table_of_contents)} chapters")
        print(f"  ✓ Title: {metadata.title}")
        print(f"  ✓ Introduction: {metadata.introduction[:100]}...")
        print(f"  ✓ TOC: {len(metadata.table_of_contents)} chapters")
        print()

    except Exception as e:
        logger.warning(f"Metadata generation failed: {e}, using fallback")
        print(f"⚠ Metadata generation failed: {e}, using fallback")
        # Fallback metadata
        metadata = type('Metadata', (), {
            'title': novel_name,
            'introduction': f"《{novel_name}》是一部九章节的小说。",
            'table_of_contents': chapter_titles
        })()
        print()

    # Step 2: Assemble complete novel using Python (deterministic, fast, complete)
    logger.info("Step 2: Assembling complete novel...")
    print("Step 2: Assembling complete novel...")

    # Read all chapters
    chapter_contents = []
    for i in range(1, 10):
        chapter_file = novel_dir / f"chapter_{i:02d}.md"
        if chapter_file.exists():
            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()
                chapter_contents.append(content)
                logger.info(f"  Read chapter {i}: {len(content)} characters")
        else:
            logger.error(f"  Chapter {i} not found!")

    logger.info(f"Read {len(chapter_contents)} chapters total")
    print(f"  ✓ Read {len(chapter_contents)} chapters")

    # Assemble the novel (deterministic string concatenation)
    novel_parts = []

    # Title
    novel_parts.append(f"# {metadata.title}\n")

    # Introduction
    novel_parts.append(f"## 简介\n{metadata.introduction}\n")

    # Table of Contents
    novel_parts.append("## 目录\n")
    for toc_entry in metadata.table_of_contents:
        novel_parts.append(toc_entry)
    novel_parts.append("")  # Empty line after TOC

    # Main content
    novel_parts.append("## 正文\n")
    for i, chapter_content in enumerate(chapter_contents, 1):
        novel_parts.append(chapter_content)
        if i < len(chapter_contents):
            novel_parts.append("\n\n")  # Separator between chapters

    # Ending marker
    novel_parts.append("\n[全书完]")

    final_book_text = "\n".join(novel_parts)

    logger.info(f"Assembled novel: {len(final_book_text)} characters")
    print(f"  ✓ Assembled {len(final_book_text)} characters")
    print()

    # Step 3: Quality review using LLM (optional but recommended)
    logger.info("Step 3: Running quality review...")
    print("Step 3: Running quality review...")

    try:
        # Combine chapters for review
        complete_book = "\n\n".join(chapters)

        final_crew = FinalCrew()
        final_result = final_crew.finalize_book(
            book_text=complete_book,
            story_bible=current_bible,
            story_spec=story_spec
        )

        final_report = final_result.get('final_report', {})
        success = final_result.get('success', False)

        # Convert Pydantic report to dict if needed
        if hasattr(final_report, 'model_dump'):
            final_report = final_report.model_dump()

        logger.info(f"Quality review completed. Passed: {success}")
        print(f"  ✓ Quality review completed. Passed: {success}")
        print()

    except Exception as e:
        logger.warning(f"Quality review failed: {e}")
        print(f"⚠ Quality review failed: {e}")
        final_report = {}
        success = False
        print()

    # Save final book with title-based filename
    # Sanitize title for filename (remove special characters)
    safe_title = "".join(c for c in metadata.title if c.isalnum() or c in (' ', '-', '_'))
    safe_title = safe_title.replace(' ', '_')
    final_book_file = novel_dir / f"{safe_title}_final.md"

    with open(final_book_file, "w", encoding="utf-8") as f:
        f.write(final_book_text)
    logger.info(f"Saved complete novel to {final_book_file}")
    logger.info(f"Final novel length: {len(final_book_text)} characters")
    print(f"✓ Saved complete novel to {final_book_file}")

    # Save final report
    with open(novel_dir / "final_report.json", "w", encoding="utf-8") as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved final report to {novel_dir / 'final_report.json'}")
    print(f"✓ Saved final report to {novel_dir / 'final_report.json'}")

    # Save metadata for reference
    metadata_dict = {
        "title": metadata.title,
        "introduction": metadata.introduction,
        "table_of_contents": metadata.table_of_contents
    }
    with open(novel_dir / "novel_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved metadata to {novel_dir / 'novel_metadata.json'}")
    print(f"✓ Saved metadata to {novel_dir / 'novel_metadata.json'}")
    print()

    if success:
        logger.info("✓✓✓ Novel generation complete and passed quality gates! ✓✓✓")
        print("\\n✓✓✓ Novel generation complete and passed quality gates! ✓✓✓")
    else:
        logger.warning("Novel generation complete but did not pass all quality gates")
        if final_report.get('issues'):
            logger.warning(f"Issues: {[issue.get('note') for issue in final_report.get('issues', [])]}")
        print("\\n⚠ Novel generation complete but did not pass all quality gates")
        if final_report.get('issues'):
            print(f"  Issues: {[issue.get('note') for issue in final_report.get('issues', [])]}")

    print()
    print("=" * 80)
    print("Generation Summary")
    print("=" * 80)
    print(f"Novel Name: {novel_name}")
    print(f"Chapters generated: {len(chapters)}/9")
    print(f"Quality gate passed: {'Yes' if success else 'No'}")
    print(f"Novel directory: {novel_dir.absolute()}")
    print("=" * 80)

    generation_metadata['end_time'] = datetime.now().isoformat()
    generation_metadata['success'] = success

    logger.info("=" * 80)
    logger.info("Generation Summary")
    logger.info("=" * 80)
    logger.info(f"Novel Name: {novel_name}")
    logger.info(f"Chapters generated: {len(chapters)}/9")
    logger.info(f"Quality gate passed: {'Yes' if success else 'No'}")
    logger.info(f"Novel directory: {novel_dir.absolute()}")
    logger.info(f"Start time: {generation_metadata['start_time']}")
    logger.info(f"End time: {generation_metadata['end_time']}")
    logger.info("=" * 80)
    logger.info("StoryCrew Novel Generation Completed")
    logger.info("=" * 80)

    with open(novel_dir / "generation_metadata.json", "w", encoding="utf-8") as f:
        json.dump(generation_metadata, f, ensure_ascii=False, indent=2)

    return {
        'success': success,
        'final_book': final_book_text,
        'metadata': generation_metadata,
        'novel_name': novel_name,
        'novel_dir': str(novel_dir.absolute())
    }


def interactive_input() -> tuple:
    """
    Interactive CLI for story generation.

    Returns:
        tuple: (genre, theme_statement, additional_preferences)
    """
    print("=" * 80)
    print("StoryCrew - AI小说自动生成系统")
    print("=" * 80)
    print()

    # Genre selection
    print("请选择小说题材：")
    print("  1. 都市职场爱情 (romance)")
    print("  2. 本格/社会派悬疑 (mystery)")
    print()

    while True:
        choice = input("请输入选择 (1/2): ").strip()
        if choice == "1":
            genre = "romance"
            genre_name = "都市职场爱情"
            break
        elif choice == "2":
            genre = "mystery"
            genre_name = "本格/社会派悬疑"
            break
        else:
            print("无效选择，请输入 1 或 2")

    print(f"✓ 已选择题材：{genre_name}")
    print()

    # Theme input
    print("请输入小说主题（建议100字左右，描述你想写的故事核心）：")
    print("提示：可以是人物关系、核心冲突、或者一句话概括的故事梗概")
    print()

    while True:
        theme = input("主题: ").strip()
        if len(theme) > 0:
            break
        print("主题不能为空，请重新输入")

    print(f"✓ 主题：{theme}")
    print()

    # Optional preferences
    print("可选：其他偏好要求（如特定人物设定、故事风格等，直接回车跳过）")
    preferences = input("偏好: ").strip()

    if preferences:
        print(f"✓ 偏好：{preferences}")
    else:
        print("✓ 无额外偏好")
    print()

    return genre, theme, preferences


def main():
    """
    Main entry point for command-line usage.

    Interactive mode (default):
        python -m storycrew.main

    Command-line mode (for scripting):
        python -m storycrew.main --genre romance --theme "..."
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="StoryCrew: Generate novels with CrewAI"
    )
    parser.add_argument(
        "--genre",
        type=str,
        choices=["romance", "mystery"],
        help="Story genre (skip for interactive mode)"
    )
    parser.add_argument(
        "--theme",
        type=str,
        help="Core theme of the story (skip for interactive mode)"
    )
    parser.add_argument(
        "--preferences",
        type=str,
        default="",
        help="Additional user preferences"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Base output directory (default: ./novels)"
    )

    args = parser.parse_args()

    # Interactive mode if no genre/theme provided
    if not args.genre or not args.theme:
        genre, theme, preferences = interactive_input()
        additional_preferences = preferences or args.preferences
        base_output_dir = args.output or "./novels"
    else:
        # Command-line mode
        genre = args.genre
        theme = args.theme
        additional_preferences = args.preferences
        base_output_dir = args.output or "./novels"

    try:
        result = run(
            genre=genre,
            theme_statement=theme,
            additional_preferences=additional_preferences,
            output_dir=base_output_dir
        )
        return 0 if result['success'] else 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
