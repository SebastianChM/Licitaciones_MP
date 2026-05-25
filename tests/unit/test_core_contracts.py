from pathlib import Path

from core.context import PipelineContext
from core.contracts import BaseStage, StageResult
from utils.config import Config


def test_pipeline_context_initialization():
    config = Config()
    ctx = PipelineContext(config=config)
    assert ctx.run_id is not None
    assert type(ctx.run_id) is str
    assert len(ctx.run_id) > 10

def test_pipeline_context_artifacts():
    config = Config()
    ctx = PipelineContext(config=config)
    test_path = Path("/tmp/test.txt")
    
    ctx.add_artifact("test", test_path)
    assert ctx.get_artifact("test") == test_path
    assert ctx.get_artifact("missing") is None

def test_stage_result_creation():
    res = StageResult(
        success=True,
        stage_name="test_stage",
        metrics_produced={"count": 10}
    )
    assert res.success is True
    assert res.stage_name == "test_stage"
    assert res.metrics_produced["count"] == 10
    
def test_base_stage_protocol():
    class DummyStage(BaseStage):
        @property
        def name(self) -> str:
            return "dummy"

        def _execute(self, context: PipelineContext) -> StageResult:
            return StageResult(success=True, stage_name=self.name)

    stage = DummyStage()
    ctx = PipelineContext(config=Config())
    assert stage.name == "dummy"
    assert stage.validate_inputs(ctx) is True
    assert stage.run(ctx).success is True
