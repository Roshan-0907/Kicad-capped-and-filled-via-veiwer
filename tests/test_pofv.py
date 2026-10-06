"""Offline tests for the via flag logic (no running KiCad needed)."""

import sys
from pathlib import Path

from kipy.board_types import Via
from kipy.proto.board import board_types_pb2 as bt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pofv_via_3d"))

import pofv  # noqa: E402


def test_make_pofv_sets_fill_cap_and_tenting():
    via = Via()

    assert pofv.make_pofv(via)

    ps = via.proto.pad_stack
    assert ps.drill.filled == bt.VDFM_FILLED
    assert ps.drill.capped == bt.VDCM_CAPPED
    assert ps.front_outer_layers.solder_mask_mode == bt.SMM_MASKED
    assert ps.back_outer_layers.solder_mask_mode == bt.SMM_MASKED
    assert pofv.is_pofv(via)


def test_make_pofv_tents_an_untented_filled_capped_via():
    via = Via()
    ps = via.proto.pad_stack
    ps.drill.filled = bt.VDFM_FILLED
    ps.drill.capped = bt.VDCM_CAPPED
    ps.front_outer_layers.solder_mask_mode = bt.SMM_UNMASKED
    ps.back_outer_layers.solder_mask_mode = bt.SMM_UNMASKED

    assert not pofv.is_pofv(via)
    assert pofv.make_pofv(via)
    assert ps.front_outer_layers.solder_mask_mode == bt.SMM_MASKED
    assert ps.back_outer_layers.solder_mask_mode == bt.SMM_MASKED


def test_make_pofv_is_idempotent():
    via = Via()
    pofv.make_pofv(via)

    assert not pofv.make_pofv(via)


def test_clear_pofv_resets_fill_and_cap_but_keeps_tenting():
    via = Via()
    pofv.make_pofv(via)

    assert pofv.clear_pofv(via)

    ps = via.proto.pad_stack
    assert ps.drill.filled == bt.VDFM_FROM_DESIGN_RULES
    assert ps.drill.capped == bt.VDCM_FROM_DESIGN_RULES
    assert ps.front_outer_layers.solder_mask_mode == bt.SMM_MASKED
    assert not pofv.clear_pofv(via)


class FakeBoard:
    def __init__(self, vias, selection):
        self._vias = vias
        self._selection = selection

    def get_vias(self):
        return self._vias

    def get_selection(self):
        return self._selection


def test_target_vias_prefers_selected_vias():
    a, b = Via(), Via()
    board = FakeBoard([a, b], [b, object()])

    assert pofv.target_vias(board, use_all=False) == [b]
    assert pofv.target_vias(board, use_all=True) == [a, b]


def test_target_vias_falls_back_to_all_when_no_via_selected():
    a, b = Via(), Via()
    board = FakeBoard([a, b], [object()])

    assert pofv.target_vias(board, use_all=False) == [a, b]
