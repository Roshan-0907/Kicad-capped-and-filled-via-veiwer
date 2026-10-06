"""Mark vias as filled & capped (POFV / IPC-4761 Type VII) with solder mask on top.

KiCad 10.0.6 and newer draw a via whose drill is *capped* without a hole in the
3D viewer, so with the solder mask tented over it the via looks exactly like a
trace under solder mask.  "Filling" on its own is not enough: the 3D viewer
still shows the hole.  This module sets all three properties on each via in one
undoable step:

    drill filling      -> filled
    drill capping      -> capped
    front/back mask    -> tented (solder mask covers the via)

The vias acted on are the selected ones, or every via on the board when no via
is selected.

Run from KiCad through the toolbar buttons defined in plugin.json, or from a
terminal against a running KiCad with the API server enabled:

    python pofv.py apply [--all]
    python pofv.py clear [--all]
"""

import argparse
import sys

from kipy import KiCad
from kipy.board_types import Via
from kipy.proto.board import board_types_pb2 as bt

# First KiCad release whose 3D viewer hides the hole of capped vias
# (https://gitlab.com/kicad/code/kicad/-/issues/23370).
FIRST_GOOD_VERSION = (10, 0, 6)


def is_pofv(via: Via) -> bool:
    """True if the via is filled, capped and tented on both sides."""
    ps = via.proto.pad_stack
    return (
        ps.drill.filled == bt.VDFM_FILLED
        and ps.drill.capped == bt.VDCM_CAPPED
        and ps.front_outer_layers.solder_mask_mode == bt.SMM_MASKED
        and ps.back_outer_layers.solder_mask_mode == bt.SMM_MASKED
    )


def make_pofv(via: Via) -> bool:
    """Set the via to filled, capped and tented.  Returns True if anything changed."""
    if is_pofv(via):
        return False

    ps = via.proto.pad_stack
    ps.drill.filled = bt.VDFM_FILLED
    ps.drill.capped = bt.VDCM_CAPPED
    ps.front_outer_layers.solder_mask_mode = bt.SMM_MASKED
    ps.back_outer_layers.solder_mask_mode = bt.SMM_MASKED
    return True


def clear_pofv(via: Via) -> bool:
    """Return filling and capping to the board default.  Tenting is left alone
    because the original setting is not recorded.  Returns True if anything changed."""
    drill = via.proto.pad_stack.drill
    fill_is_default = drill.filled in (bt.VDFM_UNKNOWN, bt.VDFM_FROM_DESIGN_RULES)
    cap_is_default = drill.capped in (bt.VDCM_UNKNOWN, bt.VDCM_FROM_DESIGN_RULES)

    if fill_is_default and cap_is_default:
        return False

    drill.filled = bt.VDFM_FROM_DESIGN_RULES
    drill.capped = bt.VDCM_FROM_DESIGN_RULES
    return True


def target_vias(board, use_all: bool) -> list:
    """Selected vias, or all vias if none are selected (or use_all is set)."""
    if not use_all:
        selected = [item for item in board.get_selection() if isinstance(item, Via)]

        if selected:
            return selected

    return list(board.get_vias())


def version_tuple(version) -> tuple:
    return (version.major, version.minor, version.patch)


def run(mode: str, use_all: bool = False) -> int:
    kicad = KiCad()
    board = kicad.get_board()
    vias = target_vias(board, use_all)

    if not vias:
        print("No vias found on the board.", file=sys.stderr)
        return 0

    change = make_pofv if mode == "apply" else clear_pofv
    changed = [via for via in vias if change(via)]

    if changed:
        if mode == "apply":
            message = f"Set {len(changed)} vias to filled & capped (POFV)"
        else:
            message = f"Removed filled & capped from {len(changed)} vias"

        commit = board.begin_commit()

        try:
            board.update_items(changed)
        except Exception:
            board.drop_commit(commit)
            raise

        board.push_commit(commit, message)
        print(f"{message}; {len(vias) - len(changed)} already up to date.")
    else:
        print(f"All {len(vias)} vias already up to date.")

    version = kicad.get_version()

    if mode == "apply" and version_tuple(version) < FIRST_GOOD_VERSION:
        # KiCad shows a plugin's stderr output to the user.
        print(
            f"Vias are marked filled & capped, but KiCad {version.major}.{version.minor}."
            f"{version.patch} still draws their holes in the 3D viewer. "
            "Update to KiCad 10.0.6 or newer to see them filled.",
            file=sys.stderr,
        )

    return 0


def main(argv=None, mode=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    if mode is None:
        parser.add_argument("mode", choices=["apply", "clear"])

    parser.add_argument(
        "--all", action="store_true", help="act on every via even if some are selected"
    )
    args = parser.parse_args(argv)
    return run(mode or args.mode, args.all)


if __name__ == "__main__":
    sys.exit(main())
