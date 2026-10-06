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
from kipy.board_types import BoardCircle, Via
from kipy.geometry import Vector2
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


# Marker layers.  A tented, filled and capped via is the same copper under the same mask
# as a zone or trace, so in the 3D viewer it cannot be told apart from them.  The marker is
# a filled disc the size of the via on a layer that is not a fabrication output, drawn by the
# 3D viewer in whatever colour the layer has there.
#
# The 3D viewer only puts layers *above* the board on the front for F.* and User.* layers
# and below it for B.* layers, so the back marker uses B.Adhesive.
MARKER_FRONT = bt.BL_User_1
MARKER_BACK = bt.BL_B_Adhes
MARKER_LAYERS = (MARKER_FRONT, MARKER_BACK)


def marker_layers_for(via: Via) -> list:
    """Marker layers a via needs: front if it reaches F.Cu, back if it reaches B.Cu."""
    drill = via.proto.pad_stack.drill
    layers = []

    if drill.start_layer == bt.BL_F_Cu:
        layers.append(MARKER_FRONT)

    if drill.end_layer == bt.BL_B_Cu:
        layers.append(MARKER_BACK)

    return layers


def marker_key(center, radius: int, layer) -> tuple:
    return (round(center.x), round(center.y), round(radius), layer)


def make_marker(via: Via, layer) -> BoardCircle:
    radius = via.diameter // 2
    circle = BoardCircle()
    circle.layer = layer
    circle.center = via.position
    circle.radius_point = Vector2.from_xy(via.position.x + radius, via.position.y)
    circle.attributes.fill.filled = True
    circle.attributes.stroke.width = 0
    return circle


def existing_markers(board) -> dict:
    """Marker circles already on the board, by (x, y, radius, layer)."""
    found = {}

    for item in board.get_shapes():
        if isinstance(item, BoardCircle) and item.layer in MARKER_LAYERS:
            found[marker_key(item.center, item.radius(), item.layer)] = item

    return found


def run_markers(mode: str, use_all: bool = False) -> int:
    """Add (mode "mark") or remove (mode "unmark") the via markers."""
    kicad = KiCad()
    board = kicad.get_board()
    vias = target_vias(board, use_all)

    if not vias:
        print("No vias found on the board.", file=sys.stderr)
        return 0

    present = existing_markers(board)
    wanted = {}

    for via in vias:
        for layer in marker_layers_for(via):
            wanted[marker_key(via.position, via.diameter // 2, layer)] = (via, layer)

    if mode == "mark":
        new = [make_marker(via, layer) for key, (via, layer) in wanted.items() if key not in present]
        message = f"Marked {len(new)} via sides for the 3D viewer"
        action = lambda: board.create_items(new)
        count = len(new)
    else:
        old = [present[key] for key in wanted if key in present]
        message = f"Removed {len(old)} via markers"
        action = lambda: board.remove_items(old)
        count = len(old)

    if not count:
        print("Nothing to do: vias already " + ("marked." if mode == "mark" else "unmarked."))
        return 0

    commit = board.begin_commit()

    try:
        action()
    except Exception:
        board.drop_commit(commit)
        raise

    board.push_commit(commit, message)
    print(message + ".")
    return 0


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
        parser.add_argument("mode", choices=["apply", "clear", "mark", "unmark"])

    parser.add_argument(
        "--all", action="store_true", help="act on every via even if some are selected"
    )
    args = parser.parse_args(argv)
    mode = mode or args.mode

    if mode in ("mark", "unmark"):
        return run_markers(mode, args.all)

    return run(mode, args.all)


if __name__ == "__main__":
    sys.exit(main())
