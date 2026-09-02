"""Unit and integration tests for hybrid VariableBar and popovers."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication
from ui.variable_bar import VariableBar
from core.template_engine import TemplateEngine


@pytest.fixture
def var_bar(qapp):
    initial = {
        "target_ip": "10.10.10.10",
        "attacker_ip": "10.10.14.5",
        "port": "4444",
        "username": "admin",
        "password": "secretpassword",
        "domain": "corp.local",
        "ntlm_hash": "aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0",
        "wordlist": "/usr/share/wordlists/dirb/big.txt",
        "url": "http://10.10.10.10:8080/admin",
    }
    bar = VariableBar(initial)
    return bar


def test_variable_bar_hybrid_initialization(var_bar):
    # Quick inputs on the bar
    assert var_bar.txt_target.text() == "10.10.10.10"
    assert var_bar.txt_attacker.text() == "10.10.14.5"
    assert var_bar.txt_port.text() == "4444"

    # Secondary variables in popovers
    assert var_bar.popover_auth.txt_user.text() == "admin"
    assert var_bar.popover_auth.txt_pass.text() == "secretpassword"
    assert var_bar.popover_auth.txt_domain.text() == "corp.local"
    assert "aad3b" in var_bar.popover_auth.txt_hash.text()
    assert var_bar.popover_scope.txt_wordlist.text() == "/usr/share/wordlists/dirb/big.txt"
    assert var_bar.popover_scope.txt_url.text() == "http://10.10.10.10:8080/admin"

    # Backward-compatible attributes
    assert var_bar.txt_user.text() == "admin"
    assert var_bar.txt_pass.text() == "secretpassword"


def test_variable_bar_get_and_set_variables(var_bar):
    new_vars = {
        "target_ip": "192.168.1.100",
        "attacker_ip": "192.168.1.50",
        "port": "9001",
        "username": "root",
        "password": "toorpassword",
        "domain": "htb.local",
        "ntlm_hash": "hash123",
        "wordlist": "/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt",
        "url": "https://192.168.1.100:8443/api",
    }

    var_bar.set_variables(new_vars)
    res = var_bar.get_variables()

    assert res["target_ip"] == "192.168.1.100"
    assert res["attacker_ip"] == "192.168.1.50"
    assert res["port"] == "9001"
    assert res["username"] == "root"
    assert res["password"] == "toorpassword"
    assert res["domain"] == "htb.local"
    assert res["ntlm_hash"] == "hash123"
    assert res["wordlist"] == "/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt"
    assert res["url"] == "https://192.168.1.100:8443/api"


def test_variable_bar_live_signal_from_popovers(var_bar):
    received = []
    var_bar.variables_changed.connect(lambda v: received.append(v))

    # Edit a field in AuthPopover
    var_bar.popover_auth.txt_user.setText("administrator")
    assert len(received) > 0
    assert received[-1]["username"] == "administrator"

    # Edit a field in ScopePopover
    var_bar.popover_scope.txt_domain = "lab.local"
    var_bar.popover_scope.txt_url.setText("http://test.local")
    assert received[-1]["url"] == "http://test.local"


def test_variable_bar_badge_button_styling(qapp):
    empty_bar = VariableBar({"target_ip": "10.10.10.10", "attacker_ip": "10.10.14.5", "port": "4444"})

    # Initially empty auth and default scope
    assert empty_bar.btn_auth.property("class") == "VarBadgeBtn"
    assert empty_bar.btn_auth.text() == "👤 Auth ▾"

    # Setting username updates badge text and class
    empty_bar.popover_auth.txt_user.setText("pentester")
    assert empty_bar.btn_auth.property("class") == "VarBadgeBtnActive"
    assert "pentester" in empty_bar.btn_auth.text()

    # Clearing username and password reverts badge
    empty_bar.popover_auth.txt_user.setText("")
    empty_bar.popover_auth.txt_pass.setText("")
    assert empty_bar.btn_auth.property("class") == "VarBadgeBtn"


def test_template_engine_interpolates_popover_variables(var_bar):
    vars_dict = var_bar.get_variables()

    # Test template with target, port, domain, and wordlist
    tpl = "gobuster dir -u {{URL}} -w {{WORDLIST}} -d {{DOMAIN}}"
    rendered = TemplateEngine.render(tpl, vars_dict)

    assert "corp.local" in rendered
    assert "/usr/share/wordlists/dirb/big.txt" in rendered
    assert "http://10.10.10.10:8080/admin" in rendered
