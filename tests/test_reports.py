"""Testes das janelas de relatório."""

from datetime import date

import pytest

from tiktok_ops.ads.reports import Reports


def test_janela_diaria_maior_que_30_dias_e_barrada():
    with pytest.raises(ValueError, match="30 dias"):
        Reports._validar_janela(date(2026, 1, 1), date(2026, 3, 1), ["stat_time_day"])


def test_janela_horaria_so_aceita_um_dia():
    with pytest.raises(ValueError, match="1 dia"):
        Reports._validar_janela(date(2026, 1, 1), date(2026, 1, 5), ["stat_time_hour"])


def test_janela_valida_passa():
    Reports._validar_janela(date(2026, 1, 1), date(2026, 1, 30), ["stat_time_day"])
