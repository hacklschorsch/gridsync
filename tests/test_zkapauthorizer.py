# -*- coding: utf-8 -*-

from unittest.mock import Mock

import pytest
from pytest_twisted import inlineCallbacks

from gridsync.tahoe import TahoeWebError
from gridsync.zkapauthorizer import ZKAPAuthorizer


def fake_treq_request_resp_code_200(*args, **kwargs):
    fake_resp = Mock()
    fake_resp.code = 200
    fake_request = Mock(return_value=fake_resp)
    return fake_request


def fake_treq_request_resp_code_500(*args, **kwargs):
    fake_resp = Mock()
    fake_resp.code = 500
    fake_request = Mock(return_value=fake_resp)
    return fake_request


@inlineCallbacks
def test__request_url(tahoe, monkeypatch):
    fake_request = fake_treq_request_resp_code_200()
    monkeypatch.setattr("treq.request", fake_request)
    yield ZKAPAuthorizer(tahoe)._request("GET", "/test")
    assert fake_request.call_args[0][1] == (
        tahoe.nodeurl + "storage-plugins/privatestorageio-zkapauthz-v1/test"
    )


@inlineCallbacks
def test__request_headers(tahoe, monkeypatch):
    fake_request = fake_treq_request_resp_code_200()
    monkeypatch.setattr("treq.request", fake_request)
    yield ZKAPAuthorizer(tahoe)._request("GET", "/test")
    assert fake_request.call_args[1]["headers"] == {
        "Authorization": f"tahoe-lafs {tahoe.api_token}",
        "Content-Type": "application/json",
    }


@inlineCallbacks
def test_add_voucher_with_voucher(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_200())
    result = yield ZKAPAuthorizer(tahoe).add_voucher("Test1234")
    assert result == "Test1234"


@inlineCallbacks
def test_add_voucher_without_voucher(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_200())
    result = yield ZKAPAuthorizer(tahoe).add_voucher()
    assert len(result) == 44


@inlineCallbacks
def test_add_voucher_raise_tahoe_web_error(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_500())
    with pytest.raises(TahoeWebError):
        yield ZKAPAuthorizer(tahoe).add_voucher()


@inlineCallbacks
def test_get_voucher(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_200())
    monkeypatch.setattr("treq.json_content", Mock(return_value={"A": "A"}))
    result = yield ZKAPAuthorizer(tahoe).get_voucher("Test1234")
    assert result == {"A": "A"}


@inlineCallbacks
def test_get_voucher_raise_tahoe_web_error(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_500())
    monkeypatch.setattr("treq.json_content", Mock(return_value={"A": "A"}))
    with pytest.raises(TahoeWebError):
        yield ZKAPAuthorizer(tahoe).get_voucher("Test1234")


@inlineCallbacks
def test_get_vouchers(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_200())
    fake_content = {"vouchers": [{"A": "A"}, {"B": "B"}]}
    monkeypatch.setattr("treq.json_content", Mock(return_value=fake_content))
    result = yield ZKAPAuthorizer(tahoe).get_vouchers()
    assert result == [{"A": "A"}, {"B": "B"}]


@inlineCallbacks
def test_get_vouchers_raise_tahoe_web_error(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_500())
    with pytest.raises(TahoeWebError):
        yield ZKAPAuthorizer(tahoe).get_vouchers()


@pytest.mark.parametrize(
    "limit,position,expected",
    [
        [0, "", "/unblinded-token"],
        [1, "", "/unblinded-token?limit=1"],
        [0, "XXX", "/unblinded-token?position=XXX"],
        [10, "XXX", "/unblinded-token?limit=10&position=XXX"],
    ],
)
@inlineCallbacks
def test_get_zkaps_query_string(tahoe, monkeypatch, limit, position, expected):
    fake_request = fake_treq_request_resp_code_200()
    monkeypatch.setattr("treq.request", fake_request)
    monkeypatch.setattr("treq.json_content", Mock())
    yield ZKAPAuthorizer(tahoe).get_zkaps(limit, position)
    assert fake_request.call_args[0][1].endswith(expected) is True


@inlineCallbacks
def test_get_zkaps_raise_tahoe_web_error(tahoe, monkeypatch):
    monkeypatch.setattr("treq.request", fake_treq_request_resp_code_500())
    with pytest.raises(TahoeWebError):
        yield ZKAPAuthorizer(tahoe).get_zkaps()


@pytest.mark.parametrize(
    "zkap_payment_url_root,voucher,expected",
    [
        [
            "https://one.example.org/payment",
            "AAAAAAAA",
            "https://one.example.org/payment?voucher=AAAAAAAA&checksum="
            "c34ab6abb7b2bb595bc25c3b388c872fd1d575819a8f55cc689510285e212385",
        ],
        [
            "https://two.example.org/payment",
            "BBBBBBBB",
            "https://two.example.org/payment?voucher=BBBBBBBB&checksum="
            "2f858775d71cc4ece5f46f497c58c01167cd6fc301e56e935070f5e81bfe5890",
        ],
    ],
)
def test_zkap_payment_url(tahoe, zkap_payment_url_root, voucher, expected):
    zkapauthorizer = ZKAPAuthorizer(tahoe)
    zkapauthorizer.zkap_payment_url_root = zkap_payment_url_root
    url = zkapauthorizer.zkap_payment_url(voucher)
    assert url.endswith(expected) is True


def test_zkap_payment_url_empty_zkap_payment_root_url(tahoe):
    zkapauthorizer = ZKAPAuthorizer(tahoe)
    zkapauthorizer.zkap_payment_url_root = ""
    url = zkapauthorizer.zkap_payment_url("TestVoucher")
    assert url == ""
