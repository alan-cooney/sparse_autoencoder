"""Store Activations Hook Tests."""
from functools import partial

import torch
from transformer_lens import HookedTransformer

from sparse_autoencoder.activation_store.list_store import ListActivationStore
from sparse_autoencoder.activation_store.utils.extend_resize import resize_to_single_item_dimension
from sparse_autoencoder.src_model.store_activations_hook import store_activations_hook


def test_hook_stores_activations() -> None:
    """Test that the hook stores activations correctly."""
    store = ListActivationStore()
    model = HookedTransformer.from_pretrained("tiny-stories-1M")

    model.add_hook(
        "blocks.1.mlp.hook_post",
        partial(
            store_activations_hook, store=store, reshape_method=resize_to_single_item_dimension
        ),
    )

    tokens = model.to_tokens("Hello world")
    logits = model.forward(tokens, stop_at_layer=2)  # type: ignore

    number_of_tokens = tokens.numel()
    mlp_size: int = model.cfg.d_mlp  # type: ignore

    assert len(store) == number_of_tokens
    assert store[0].shape[0] == mlp_size
    assert torch.is_tensor(logits)  # Check the forward pass completed
