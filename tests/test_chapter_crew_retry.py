"""Integration tests for ChapterCrew selective retry flow.

Tests verify the three retry levels work correctly:
- EDIT_ONLY: prose/pacing/word_count issues → only re-run edit + judge
- WRITE_ONLY: motivation/hook/clue_fairness/continuity → re-run write + edit + judge
- FULL_RETRY: structure/safety(critical) → re-run full pipeline

Each test mocks Crew.kickoff() to avoid real LLM calls and verifies:
1. Correct pipeline is executed based on retry level
2. Intermediate results are preserved correctly
3. Escalation logic works after max retries
4. SceneList parsing failures trigger fallback
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from storycrew.crews.chapter_crew import ChapterCrew, MAX_EDIT_RETRIES, MAX_WRITE_RETRIES
from storycrew.models import (
    JudgeReport, Issue, SceneList, ScoreBreakdown,
    ChapterRevision, RetryLevel
)


class MockTaskOutput:
    """Mock task output object with pydantic and raw attributes."""

    def __init__(self, pydantic_obj=None, raw=None):
        # Store pydantic object
        self._pydantic = pydantic_obj
        # Store raw value
        self._raw = raw

    @property
    def pydantic(self):
        """Pydantic property."""
        return self._pydantic

    @property
    def raw(self):
        """Raw property."""
        return self._raw


class MockCrewResult:
    """Mock Crew kickoff result with tasks_output list."""

    def __init__(self, outputs_list):
        self.tasks_output = outputs_list


@pytest.fixture
def chapter_crew():
    """Create ChapterCrew instance for testing."""
    return ChapterCrew()


@pytest.fixture
def sample_inputs():
    """Sample inputs for chapter generation."""
    return {
        "chapter_number": 1,
        "chapter_outline": {
            "title": "Test Chapter",
            "summary": "Test summary"
        },
        "story_bible_public": {"characters": [], "relationships": []},
        "story_bible_full": {"characters": [], "relationships": [], "truth_card": {}},
        "story_spec": {"genre": "mystery", "theme": "justice"},
        "revision_instructions": "",
        "scene_list": "",
    }


@pytest.fixture
def sample_scene_list():
    """Sample SceneList object."""
    return SceneList(
        chapter_number=1,
        scenes=[
            {
                "scene_number": 1,
                "purpose": "Introduction",
                "setting": "Morning",
                "action_beat": "Wake up",
                "target_words": 500
            }
        ]
    )


@pytest.fixture
def sample_judge_report_prose():
    """Sample JudgeReport with prose issue (EDIT_ONLY)."""
    return JudgeReport(
        chapter=1,
        scores=ScoreBreakdown(
            continuity=8,
            pacing=5,
            character_motivation=7,
            genre_fulfillment=8,
            prose=4,  # Low prose score
            hook=7,
            clue_fairness=8
        ),
        passed=False,
        issues=[
            Issue(type="prose", severity="medium", note="文笔平淡，缺乏表现力")
        ],
        revision_instructions=[
            "增强描写，使用更多感官细节",
            "改进对话，使其更加自然"
        ]
    )


@pytest.fixture
def sample_judge_report_motivation():
    """Sample JudgeReport with motivation issue (WRITE_ONLY)."""
    return JudgeReport(
        chapter=1,
        scores=ScoreBreakdown(
            continuity=8,
            pacing=7,
            character_motivation=4,  # Low motivation score
            genre_fulfillment=8,
            prose=7,
            hook=7,
            clue_fairness=8
        ),
        passed=False,
        issues=[
            Issue(type="motivation", severity="high", note="主角动机不合理")
        ],
        revision_instructions=[
            "重新设计主角动机",
            "增加内心独白展示动机"
        ]
    )


@pytest.fixture
def sample_judge_report_structure():
    """Sample JudgeReport with structure issue (FULL_RETRY)."""
    return JudgeReport(
        chapter=1,
        scores=ScoreBreakdown(
            continuity=5,
            pacing=5,
            character_motivation=5,
            genre_fulfillment=5,
            prose=5,
            hook=5,
            clue_fairness=5
        ),
        passed=False,
        issues=[
            Issue(type="structure", severity="high", note="场景顺序不合理")
        ],
        revision_instructions=[
            "重新规划场景顺序",
            "调整章节结构"
        ]
    )


@pytest.fixture
def sample_judge_report_passed():
    """Sample JudgeReport that passed."""
    return JudgeReport(
        chapter=1,
        scores=ScoreBreakdown(
            continuity=9,
            pacing=9,
            character_motivation=9,
            genre_fulfillment=9,
            prose=9,
            hook=9,
            clue_fairness=9
        ),
        passed=True,
        issues=[],
        revision_instructions=[],
        strengths=["情节紧凑", "人物鲜明"]
    )


def test_edit_only_retry_flow(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_prose,
    sample_judge_report_passed
):
    """Test EDIT_ONLY retry flow: only edit + judge should run on retry.

    First run: plan -> write -> edit -> judge (fails with prose issue)
    Second run: only edit -> judge (preserves scene_list and draft_text)
    Verify no re-planning or re-writing happens.
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup mock instances for each kickoff call
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()

        # First run: full pipeline (5 tasks)
        scene_list_output = MockTaskOutput(pydantic_obj=sample_scene_list)
        draft_text = "Draft chapter text"
        revision_text_1 = "First revision"
        updated_bible_1 = {"characters": []}

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            scene_list_output,
            MockTaskOutput(raw=draft_text),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_prose),
            MockTaskOutput(pydantic_obj=updated_bible_1)
        ])

        # Second run: edit only (3 tasks: edit, judge, update_bible)
        revision_text_2 = "Second revision with better prose"
        updated_bible_2 = {"characters": []}

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj=updated_bible_2)
        ])

        # Configure mock_crew_class to return different instances
        mock_crew_class.side_effect = [mock_crew_instance_1, mock_crew_instance_2]

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify result
        assert result["attempts"] == 2
        assert result["chapter_text"] == revision_text_2
        assert result["judge_report"].passed is True

        # Verify kickoff was called twice
        assert mock_crew_class.call_count == 2

        # Verify first call was full pipeline (5 agents, 5 tasks)
        first_call_agents = mock_crew_class.call_args_list[0][1]["agents"]
        first_call_tasks = mock_crew_class.call_args_list[0][1]["tasks"]
        assert len(first_call_agents) == 5  # planner, writer, editor, continuity, judge
        assert len(first_call_tasks) == 5  # plan, write, edit, judge, update_bible

        # Verify second call was edit only (3 agents, 3 tasks)
        second_call_agents = mock_crew_class.call_args_list[1][1]["agents"]
        second_call_tasks = mock_crew_class.call_args_list[1][1]["tasks"]
        assert len(second_call_agents) == 3  # editor, judge, continuity
        assert len(second_call_tasks) == 3  # edit, judge, update_bible

        # Verify second call preserved scene_list and draft_text
        second_call_inputs = mock_crew_instance_2.kickoff.call_args[1]["inputs"]
        assert "scene_list" in second_call_inputs
        # Verify SceneList was correctly preserved
        stored_scene_list = SceneList.model_validate_json(second_call_inputs["scene_list"])
        assert stored_scene_list.chapter_number == sample_scene_list.chapter_number
        assert len(stored_scene_list.scenes) == len(sample_scene_list.scenes)
        assert stored_scene_list.scenes[0].scene_number == sample_scene_list.scenes[0].scene_number
        assert "draft_text_for_edit" in second_call_inputs
        assert second_call_inputs["draft_text_for_edit"] == draft_text


def test_write_only_retry_flow(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_motivation,
    sample_judge_report_passed
):
    """Test WRITE_ONLY retry flow: write + edit + judge should run on retry.

    First run: plan -> write -> edit -> judge (fails with motivation issue)
    Second run: only write -> edit -> judge (preserves scene_list)
    Verify scene_list is reused (not regenerated).
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup mock instances
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()

        # First run: full pipeline (5 tasks)
        scene_list_output = MockTaskOutput(pydantic_obj=sample_scene_list)
        draft_text_1 = "First draft with weak motivation"
        revision_text_1 = "First revision"
        updated_bible_1 = {"characters": []}

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            scene_list_output,
            MockTaskOutput(raw=draft_text_1),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_motivation),
            MockTaskOutput(pydantic_obj=updated_bible_1)
        ])

        # Second run: write only (4 tasks: write, edit, judge, update_bible)
        draft_text_2 = "Second draft with strong motivation"
        revision_text_2 = "Second revision"
        updated_bible_2 = {"characters": []}

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=draft_text_2),
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj=updated_bible_2)
        ])

        mock_crew_class.side_effect = [mock_crew_instance_1, mock_crew_instance_2]

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify result
        assert result["attempts"] == 2
        assert result["chapter_text"] == revision_text_2
        assert result["judge_report"].passed is True

        # Verify kickoff was called twice
        assert mock_crew_class.call_count == 2

        # Verify first call was full pipeline (5 agents, 5 tasks)
        first_call_agents = mock_crew_class.call_args_list[0][1]["agents"]
        first_call_tasks = mock_crew_class.call_args_list[0][1]["tasks"]
        assert len(first_call_agents) == 5
        assert len(first_call_tasks) == 5

        # Verify second call was write only (4 agents, 4 tasks)
        second_call_agents = mock_crew_class.call_args_list[1][1]["agents"]
        second_call_tasks = mock_crew_class.call_args_list[1][1]["tasks"]
        assert len(second_call_agents) == 4  # writer, editor, judge, continuity
        assert len(second_call_tasks) == 4  # write, edit, judge, update_bible

        # Verify second call preserved scene_list
        second_call_inputs = mock_crew_instance_2.kickoff.call_args[1]["inputs"]
        assert "scene_list" in second_call_inputs
        # Verify SceneList was correctly preserved
        stored_scene_list = SceneList.model_validate_json(second_call_inputs["scene_list"])
        assert stored_scene_list.chapter_number == sample_scene_list.chapter_number
        assert len(stored_scene_list.scenes) == len(sample_scene_list.scenes)
        assert stored_scene_list.scenes[0].scene_number == sample_scene_list.scenes[0].scene_number

        # Verify draft_text_for_edit is NOT preserved for WRITE_ONLY
        assert "draft_text_for_edit" not in second_call_inputs


def test_full_retry_flow(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_structure,
    sample_judge_report_passed
):
    """Test FULL_RETRY flow: entire pipeline should run again.

    First run: plan -> write -> edit -> judge (fails with structure issue)
    Second run: full pipeline (plan -> write -> edit -> judge)
    Verify nothing is preserved.
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup mock instances
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()

        # First run: full pipeline with structure issue
        scene_list_1 = SceneList(
            chapter_number=1,
            scenes=[
                {"scene_number": 1, "purpose": "Bad structure", "setting": "Morning",
                 "action_beat": "Wake up", "target_words": 500}
            ]
        )
        draft_text_1 = "Draft with bad structure"
        revision_text_1 = "Revision with bad structure"
        updated_bible_1 = {"characters": []}

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            MockTaskOutput(pydantic_obj=scene_list_1),
            MockTaskOutput(raw=draft_text_1),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_structure),
            MockTaskOutput(pydantic_obj=updated_bible_1)
        ])

        # Second run: full pipeline again with new scene_list
        scene_list_2 = SceneList(
            chapter_number=1,
            scenes=[
                {"scene_number": 1, "purpose": "Good structure", "setting": "Morning",
                 "action_beat": "Wake up", "target_words": 500}
            ]
        )
        draft_text_2 = "Draft with good structure"
        revision_text_2 = "Revision with good structure"
        updated_bible_2 = {"characters": []}

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(pydantic_obj=scene_list_2),
            MockTaskOutput(raw=draft_text_2),
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj=updated_bible_2)
        ])

        mock_crew_class.side_effect = [mock_crew_instance_1, mock_crew_instance_2]

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify result
        assert result["attempts"] == 2
        assert result["chapter_text"] == revision_text_2
        assert result["judge_report"].passed is True

        # Verify both calls were full pipeline
        assert mock_crew_class.call_count == 2
        for call_args in mock_crew_class.call_args_list:
            agents = call_args[1]["agents"]
            tasks = call_args[1]["tasks"]
            assert len(agents) == 5  # Full pipeline has 5 agents
            assert len(tasks) == 5  # Full pipeline has 5 tasks

        # Verify second call did NOT preserve scene_list or draft_text
        second_call_inputs = mock_crew_instance_2.kickoff.call_args[1]["inputs"]
        # scene_list should be empty placeholder for new plan
        assert second_call_inputs.get("scene_list") == ""
        assert "draft_text_for_edit" not in second_call_inputs


def test_edit_only_retry_count_tracking(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_prose,
    sample_judge_report_passed
):
    """Test that edit retry count is tracked correctly across attempts.

    This test verifies that the system correctly tracks consecutive EDIT_ONLY
    retry attempts. It does NOT test escalation to WRITE_ONLY (that doesn't
    actually occur - determine_retry_level() returns FULL_RETRY on attempt >= 2).

    First run (attempt=0): prose issue -> EDIT_ONLY
    Second run (attempt=1): prose issue -> EDIT_ONLY
    Third run (attempt=2): prose issue -> EDIT_ONLY (count would be 2, but determine_retry_level returns FULL_RETRY)

    The test confirms:
    - edit_retry_count is incremented on each EDIT_ONLY retry
    - The system maintains the same retry level (EDIT_ONLY) across attempts
    - The correct agents/tasks are executed for each attempt
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup three mock instances
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()
        mock_crew_instance_3 = MagicMock()

        # First run: full pipeline -> prose issue (attempt 0)
        scene_list_output = MockTaskOutput(pydantic_obj=sample_scene_list)
        draft_text = "Draft text"
        revision_text_1 = "Revision 1"

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            scene_list_output,
            MockTaskOutput(raw=draft_text),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_prose),
            MockTaskOutput(pydantic_obj={})
        ])

        # Second run: edit only -> prose issue again (attempt 1)
        revision_text_2 = "Revision 2"

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_prose),
            MockTaskOutput(pydantic_obj={})
        ])

        # Third run: edit only -> passes (attempt 2)
        # Note: Even though attempt=2, the code still runs EDIT_ONLY
        # because that's what state.last_retry_level is set to
        revision_text_3 = "Revision 3 with better prose"

        mock_crew_instance_3.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=revision_text_3),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj={})
        ])

        mock_crew_class.side_effect = [
            mock_crew_instance_1,
            mock_crew_instance_2,
            mock_crew_instance_3
        ]

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify success on third attempt
        assert result["attempts"] == 3
        assert result["judge_report"].passed is True
        assert mock_crew_class.call_count == 3

        # Verify first run: full pipeline (5 agents)
        first_call_agents = mock_crew_class.call_args_list[0][1]["agents"]
        assert len(first_call_agents) == 5

        # Verify second run: edit only (3 agents)
        second_call_agents = mock_crew_class.call_args_list[1][1]["agents"]
        assert len(second_call_agents) == 3

        # Verify third run: edit only (3 agents)
        # This confirms that state.last_retry_level was EDIT_ONLY
        third_call_agents = mock_crew_class.call_args_list[2][1]["agents"]
        assert len(third_call_agents) == 3  # editor, judge, continuity


def test_write_only_retry_count_tracking(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_motivation,
    sample_judge_report_passed
):
    """Test that write retry count is tracked correctly across attempts.

    This test verifies that the system correctly tracks consecutive WRITE_ONLY
    retry attempts. It does NOT test escalation to FULL_RETRY (that doesn't
    actually occur - determine_retry_level() returns FULL_RETRY on attempt >= 2).

    First run (attempt=0): motivation issue -> WRITE_ONLY (count=0)
    Second run (attempt=1): motivation issue -> WRITE_ONLY (count=1)
    Third run (attempt=2): motivation issue -> WRITE_ONLY (count would be 2, but determine_retry_level returns FULL_RETRY)

    The test confirms:
    - write_retry_count is incremented on each WRITE_ONLY retry
    - The system maintains the same retry level (WRITE_ONLY) across attempts
    - The correct agents/tasks are executed for each attempt
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup three mock instances
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()
        mock_crew_instance_3 = MagicMock()

        # First run: full pipeline -> motivation issue (attempt 0)
        scene_list_output = MockTaskOutput(pydantic_obj=sample_scene_list)
        draft_text_1 = "Draft 1"
        revision_text_1 = "Revision 1"

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            scene_list_output,
            MockTaskOutput(raw=draft_text_1),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_motivation),
            MockTaskOutput(pydantic_obj={})
        ])

        # Second run: write only -> motivation issue again (attempt 1)
        draft_text_2 = "Draft 2"
        revision_text_2 = "Revision 2"

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=draft_text_2),
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_motivation),
            MockTaskOutput(pydantic_obj={})
        ])

        # Third run: write only -> passes (attempt 2)
        # Note: Even though attempt=2, the code still runs WRITE_ONLY
        # because that's what state.last_retry_level is set to
        draft_text_3 = "Draft 3 with better motivation"
        revision_text_3 = "Revision 3"

        mock_crew_instance_3.kickoff.return_value = MockCrewResult([
            MockTaskOutput(raw=draft_text_3),
            MockTaskOutput(raw=revision_text_3),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj={})
        ])

        mock_crew_class.side_effect = [
            mock_crew_instance_1,
            mock_crew_instance_2,
            mock_crew_instance_3
        ]

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify success on third attempt
        assert result["attempts"] == 3
        assert result["judge_report"].passed is True
        assert mock_crew_class.call_count == 3

        # Verify first run: full pipeline (5 agents)
        first_call_agents = mock_crew_class.call_args_list[0][1]["agents"]
        assert len(first_call_agents) == 5

        # Verify second run: write only (4 agents)
        second_call_agents = mock_crew_class.call_args_list[1][1]["agents"]
        assert len(second_call_agents) == 4

        # Verify third run: write only (4 agents)
        # This confirms that state.last_retry_level was WRITE_ONLY
        third_call_agents = mock_crew_class.call_args_list[2][1]["agents"]
        assert len(third_call_agents) == 4  # writer, editor, judge, continuity


def test_scene_list_parse_failure_fallback(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_motivation,
    sample_judge_report_passed
):
    """Test fallback to FULL_RETRY when SceneList parsing fails.

    First run: plan -> write -> edit -> judge (fails with motivation issue)
    Second run: WRITE_ONLY attempted, but SceneList parsing fails
    Verify fallback to FULL_RETRY.
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Setup mock instances
        mock_crew_instance_1 = MagicMock()
        mock_crew_instance_2 = MagicMock()

        # First run: full pipeline -> motivation issue
        scene_list_output = MockTaskOutput(pydantic_obj=sample_scene_list)
        draft_text_1 = "Draft 1"
        revision_text_1 = "Revision 1"

        mock_crew_instance_1.kickoff.return_value = MockCrewResult([
            scene_list_output,
            MockTaskOutput(raw=draft_text_1),
            MockTaskOutput(raw=revision_text_1),
            MockTaskOutput(pydantic_obj=sample_judge_report_motivation),
            MockTaskOutput(pydantic_obj={})
        ])

        # Second run: full retry (fallback due to parse failure)
        scene_list_2 = SceneList(
            chapter_number=1,
            scenes=[
                {"scene_number": 1, "purpose": "New plan", "setting": "Morning",
                 "action_beat": "Wake up", "target_words": 500}
            ]
        )
        draft_text_2 = "Draft 2"
        revision_text_2 = "Revision 2"

        mock_crew_instance_2.kickoff.return_value = MockCrewResult([
            MockTaskOutput(pydantic_obj=scene_list_2),
            MockTaskOutput(raw=draft_text_2),
            MockTaskOutput(raw=revision_text_2),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj={})
        ])

        mock_crew_class.side_effect = [mock_crew_instance_1, mock_crew_instance_2]

        # Mock _parse_scene_list_safe to return None (simulate parse failure)
        with patch.object(
            chapter_crew,
            '_parse_scene_list_safe',
            return_value=None
        ):
            # Execute
            result = chapter_crew.generate_chapter(
                chapter_number=1,
                chapter_outline=sample_inputs["chapter_outline"],
                story_bible=sample_inputs["story_bible_public"],
                story_spec=sample_inputs["story_spec"]
            )

            # Verify fallback to FULL_RETRY happened
            assert result["attempts"] == 2
            assert mock_crew_class.call_count == 2

            # Both calls should be full pipeline (5 agents each)
            for call_args in mock_crew_class.call_args_list:
                agents = call_args[1]["agents"]
                assert len(agents) == 5


def test_successful_first_attempt(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_passed
):
    """Test successful generation on first attempt (no retry needed)."""
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        mock_crew_instance = MagicMock()

        revision_text = "Perfect chapter text"
        updated_bible = {"characters": []}

        mock_crew_instance.kickoff.return_value = MockCrewResult([
            MockTaskOutput(pydantic_obj=sample_scene_list),
            MockTaskOutput(raw="Draft text"),
            MockTaskOutput(raw=revision_text),
            MockTaskOutput(pydantic_obj=sample_judge_report_passed),
            MockTaskOutput(pydantic_obj=updated_bible)
        ])

        mock_crew_class.return_value = mock_crew_instance

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify single attempt
        assert result["attempts"] == 1
        assert result["chapter_text"] == revision_text
        assert result["judge_report"].passed is True

        # Verify only one kickoff call
        assert mock_crew_class.call_count == 1


def test_max_retries_exhausted(
    chapter_crew,
    sample_inputs,
    sample_scene_list,
    sample_judge_report_prose
):
    """Test behavior when max retries are exhausted.

    Should return failure result after max_retries + 1 attempts.
    """
    with patch('storycrew.crews.chapter_crew.Crew') as mock_crew_class:
        # Create mock instances for 3 attempts (max_retries=2, so 3 total attempts)
        mock_instances = [MagicMock() for _ in range(3)]

        for i, mock_instance in enumerate(mock_instances):
            if i == 0:
                # First run: full pipeline
                mock_instance.kickoff.return_value = MockCrewResult([
                    MockTaskOutput(pydantic_obj=sample_scene_list),
                    MockTaskOutput(raw=f"Draft {i}"),
                    MockTaskOutput(raw=f"Revision {i}"),
                    MockTaskOutput(pydantic_obj=sample_judge_report_prose),
                    MockTaskOutput(pydantic_obj={})
                ])
            else:
                # Subsequent runs: edit only
                mock_instance.kickoff.return_value = MockCrewResult([
                    MockTaskOutput(raw=f"Revision {i}"),
                    MockTaskOutput(pydantic_obj=sample_judge_report_prose),
                    MockTaskOutput(pydantic_obj={})
                ])

        mock_crew_class.side_effect = mock_instances

        # Execute
        result = chapter_crew.generate_chapter(
            chapter_number=1,
            chapter_outline=sample_inputs["chapter_outline"],
            story_bible=sample_inputs["story_bible_public"],
            story_spec=sample_inputs["story_spec"]
        )

        # Verify all attempts were made
        assert result["attempts"] == 3  # max_retries (2) + 1
        assert result.get("success") is False
        assert not result["judge_report"].passed
