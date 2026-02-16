from communication.core.template_engine import TemplateEngine


def test_template_rendering_with_variables():
    engine = TemplateEngine()
    output = engine.render(
        "Hello {{student_name}} Batch {{batch}} moved to {{time}}",
        {"student_name": "Riya", "batch": "A1", "time": "5PM"},
        "telegram",
    )
    assert "Riya" in output
    assert "A1" in output
    assert "5PM" in output
