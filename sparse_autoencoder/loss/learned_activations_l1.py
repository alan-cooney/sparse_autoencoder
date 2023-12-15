"""Learned activations L1 (absolute error) loss."""
from typing import final

from jaxtyping import Float
import torch
from torch import Tensor

from sparse_autoencoder.loss.abstract_loss import AbstractLoss, LossLogType, LossReductionType
from sparse_autoencoder.tensor_types import Axis


@final
class LearnedActivationsL1Loss(AbstractLoss):
    """Learned activations L1 (absolute error) loss.

    L1 loss penalty is the absolute sum of the learned activations. The L1 penalty is this
    multiplied by the l1_coefficient (designed to encourage sparsity).

    Example:
        >>> l1_loss = LearnedActivationsL1Loss(0.1)
        >>> learned_activations = torch.tensor([[2.0, -3], [2.0, -3]])
        >>> unused_activations = torch.zeros_like(learned_activations)
        >>> # Returns loss and metrics to log
        >>> l1_loss(unused_activations, learned_activations, unused_activations)[0]
        tensor(0.5000)
    """

    l1_coefficient: float | Float[Tensor, Axis.names(Axis.COMPONENT_OPTIONAL)]
    """L1 coefficient."""

    def log_name(self) -> str:
        """Log name.

        Returns:
            Name of the loss module for logging.
        """
        return "learned_activations_l1_loss_penalty"

    def __init__(
        self, l1_coefficient: float | Float[Tensor, Axis.names(Axis.COMPONENT_OPTIONAL)]
    ) -> None:
        """Initialize the absolute error loss.

        Args:
            l1_coefficient: L1 coefficient. The original paper experimented with L1 coefficients of
                [0.01, 0.008, 0.006, 0.004, 0.001]. They used 250 tokens per prompt, so as an
                approximate guide if you use e.g. 2x this number of tokens you might consider using
                0.5x the l1 coefficient.
        """
        self.l1_coefficient = l1_coefficient
        super().__init__()

    def _l1_loss(
        self,
        source_activations: Float[  # noqa: ARG002
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
        learned_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.LEARNT_FEATURE)
        ],
        decoded_activations: Float[  # noqa: ARG002s
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
    ) -> tuple[
        Float[Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL)],
        Float[Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL)],
    ]:
        """Learned activations L1 (absolute error) loss.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.

        Returns:
            Tuple of itemwise absolute loss, and itemwise absolute loss multiplied by the l1
            coefficient.
        """
        # Absolute loss is the summed absolute value of the learned activations (i.e. over the
        # learned feature axis).
        absolute_loss: Float[Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL)] = torch.abs(
            learned_activations
        ).sum(dim=-1)

        absolute_loss_penalty: Float[Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL)] = (
            absolute_loss * self.l1_coefficient
        )

        return absolute_loss, absolute_loss_penalty

    def forward(
        self,
        source_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
        learned_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.LEARNT_FEATURE)
        ],
        decoded_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
    ) -> Float[Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL)]:
        """Learned activations L1 (absolute error) loss.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.

        Returns:
            Loss per batch item.
        """
        return self._l1_loss(source_activations, learned_activations, decoded_activations)[1]

    # Override to add both the loss and the penalty to the log
    def batch_scalar_loss_with_log(
        self,
        source_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
        learned_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.LEARNT_FEATURE)
        ],
        decoded_activations: Float[
            Tensor, Axis.names(Axis.BATCH, Axis.COMPONENT_OPTIONAL, Axis.INPUT_OUTPUT_FEATURE)
        ],
        reduction: LossReductionType = LossReductionType.MEAN,
    ) -> tuple[Float[Tensor, Axis.COMPONENT_OPTIONAL], LossLogType]:
        """Learned activations L1 (absolute error) loss, with log.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.
            reduction: Loss reduction type. Typically you would choose LossReductionType.MEAN to
                make the loss independent of the batch size.

        Returns:
            Tuple of the L1 absolute error batch scalar loss and a dict of the properties to log
                (loss before and after the l1 coefficient).
        """
        absolute_loss, absolute_loss_penalty = self._l1_loss(
            source_activations, learned_activations, decoded_activations
        )

        match reduction:
            case LossReductionType.MEAN:
                batch_scalar_loss = absolute_loss.mean(0).squeeze()
                batch_scalar_loss_penalty = absolute_loss_penalty.mean(0).squeeze()
            case LossReductionType.SUM:
                batch_scalar_loss = absolute_loss.sum(0).squeeze()
                batch_scalar_loss_penalty = absolute_loss_penalty.sum(0).squeeze()

        batch_loss_to_log = batch_scalar_loss.tolist()
        batch_loss_penalty_to_log = batch_scalar_loss_penalty.tolist()

        # Create the log
        metrics = {}
        if len(batch_loss_to_log) == 1:
            metrics["train/loss/learned_activations_l1_loss"] = batch_loss_to_log[0]
            metrics[f"train/loss/{self.log_name()}"] = batch_loss_penalty_to_log[0]
        else:
            for component_idx, (component_loss, component_loss_penalty) in enumerate(
                zip(batch_loss_to_log, batch_loss_penalty_to_log)
            ):
                metrics[
                    f"train/loss/learned_activations_l1_loss/component_{component_idx}"
                ] = component_loss
                metrics[
                    f"train/loss/{self.log_name()}/component_{component_idx}"
                ] = component_loss_penalty

        return batch_scalar_loss_penalty, metrics

    def extra_repr(self) -> str:
        """Extra representation string."""
        return f"l1_coefficient={self.l1_coefficient}"
