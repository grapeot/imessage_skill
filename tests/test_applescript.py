from imessage_skill.applescript import build_doctor_command, build_send_command


def test_build_send_command_uses_participant_and_imessage() -> None:
    command = build_send_command("alice@example.com", "hello")

    assert command[0:2] == ["osascript", "-e"]
    assert "participant targetHandle" in command[2]
    assert "service type = iMessage" in command[2]
    assert command[-2:] == ["alice@example.com", "hello"]


def test_build_send_command_terminates_options_before_user_data() -> None:
    # A dash-prefixed handle or body must reach the run handler as data, not be
    # parsed by osascript as its own flag (e.g. "-e <script>").
    for handle, body in [
        ("-epayload", "hi"),
        ("alice@example.com", "-epayload"),
        ("--help", "hi"),
    ]:
        command = build_send_command(handle, body)
        assert command[3] == "--"
        assert command[4:] == [handle, body]


def test_build_doctor_command_counts_imessage_accounts() -> None:
    command = build_doctor_command()

    assert command[0:2] == ["osascript", "-e"]
    assert "accounts whose service type = iMessage" in command[2]
