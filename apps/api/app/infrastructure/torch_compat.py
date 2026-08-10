# app/infrastructure/torch_compat.py — shims for newer transformers on older torch
"""Compatibility helpers for transformers>=5 on torch builds that hide DTensor."""


def ensure_dtensor_export() -> None:
    """Ensure ``DTensor`` is importable from ``torch.distributed.tensor``.

    transformers 5.x does ``from torch.distributed.tensor import DTensor``.
    On torch 2.4.x that name lives under ``torch.distributed._tensor`` instead;
    the public ``tensor`` package does not re-export it.
    """
    import torch.distributed.tensor as public_tensor

    if hasattr(public_tensor, "DTensor"):
        return

    try:
        from torch.distributed._tensor import DTensor as _DTensor
    except Exception as exc:  # pragma: no cover - depends on torch layout
        raise ImportError(
            "DTensor is not available on this torch build. "
            f"torch={getattr(__import__('torch'), '__version__', '?')}: "
            "neither torch.distributed.tensor nor torch.distributed._tensor "
            "exports DTensor. Upgrade torch (e.g. >=2.5) or pin transformers "
            "to a version that does not require the public DTensor export."
        ) from exc

    setattr(public_tensor, "DTensor", _DTensor)
    # DeviceMesh is often imported alongside DTensor from the same public path.
    if not hasattr(public_tensor, "DeviceMesh"):
        try:
            from torch.distributed._tensor import DeviceMesh as _DeviceMesh
        except Exception:
            try:
                from torch.distributed.device_mesh import DeviceMesh as _DeviceMesh
            except Exception:
                _DeviceMesh = None
        if _DeviceMesh is not None:
            setattr(public_tensor, "DeviceMesh", _DeviceMesh)

    if not hasattr(public_tensor, "DTensor"):
        raise ImportError(
            "Failed to export DTensor onto torch.distributed.tensor "
            f"(torch={getattr(__import__('torch'), '__version__', '?')})."
        )
