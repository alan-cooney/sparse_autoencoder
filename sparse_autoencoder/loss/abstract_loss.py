"""Abstract loss."""
from abc import ABC, abstractmethod
from typing import TypeAlias, final

from jaxtyping import Float
from strenum import LowercaseStrEnum
import torch
from torch import Tensor
from torch.nn import Module

from sparse_autoencoder.tensor_types import Axis


class LossReductionType(LowercaseStrEnum):
    """Loss reduction type."""

    MEAN = "mean"

    SUM = "sum"


LossLogType: TypeAlias = dict[str, int | float | str]
"""Loss log dict."""


class AbstractLoss(Module, ABC):
    """Abstract loss interface.

    Interface for implementing batch itemwise loss functions.
    """

    _modules: dict[str, "AbstractLoss"]  # type: ignore[assignment] (narrowing)
    """Children loss modules."""

    @abstractmethod
    def log_name(self) -> str:
        """Log name.

        Returns:
            Name of the loss module for logging.
        """

    @abstractmethod
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
        """Batch itemwise loss.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.

        Returns:
            Loss per batch item.
        """

    @final
    def batch_scalar_loss(
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
    ) -> Float[Tensor, Axis.COMPONENT_OPTIONAL]:
        """Batch loss (component-wise loss).

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.
            reduction: Loss reduction type. Typically you would choose LossReductionType.MEAN to
                make the loss independent of the batch size.

        Returns:
            Loss for the batch.
        """
        itemwise_loss = self.forward(source_activations, learned_activations, decoded_activations)

        # Reduction parameter is over the batch dimension (not the component dimension)
        match reduction:
            case LossReductionType.MEAN:
                return itemwise_loss.mean(dim=0).squeeze()
            case LossReductionType.SUM:
                return itemwise_loss.sum(dim=0).squeeze()

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
        """Batch loss (component-wise loss) with logging.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.
            reduction: Loss reduction type. Typically you would choose LossReductionType.MEAN to
                make the loss independent of the batch size.

        Returns:
            Tuple of the batch scalar loss and a dict of any properties to log.
        """
        children_loss_scalars: list[Float[Tensor, Axis.COMPONENT_OPTIONAL]] = []
        metrics: LossLogType = {}

        # If the loss module has children (e.g. it is a reducer):
        if len(self._modules) > 0:
            for loss_module in self._modules.values():
                child_loss, child_metrics = loss_module.batch_scalar_loss_with_log(
                    source_activations,
                    learned_activations,
                    decoded_activations,
                    reduction=reduction,
                )
                children_loss_scalars.append(child_loss)
                metrics.update(child_metrics)

            # Get the total loss & metric
            current_module_loss = torch.stack(children_loss_scalars).sum(0)

        # Otherwise if it is a leaf loss module:
        else:
            current_module_loss = self.batch_scalar_loss(
                source_activations, learned_activations, decoded_activations, reduction
            )

        # Add in the current loss module's metric
        log_name = "train/loss/" + self.log_name()
        loss_to_log: list | float = current_module_loss.tolist()
        if isinstance(loss_to_log, float):
            metrics[log_name] = loss_to_log
        else:
            for component_idx, component_loss in enumerate(loss_to_log):
                metrics[log_name + f"/component_{component_idx}"] = component_loss

        return current_module_loss, metrics

    @final
    def __call__(
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
    ) -> tuple[Float[Tensor, Axis.SINGLE_ITEM], LossLogType]:
        """Batch scalar loss.

        Args:
            source_activations: Source activations (input activations to the autoencoder from the
                source model).
            learned_activations: Learned activations (intermediate activations in the autoencoder).
            decoded_activations: Decoded activations.
            reduction: Loss reduction type. Typically you would choose LossReductionType.MEAN to
                make the loss independent of the batch size.

        Returns:
            Tuple of the batch scalar loss and a dict of any properties to log.
        """
        return self.batch_scalar_loss_with_log(
            source_activations, learned_activations, decoded_activations, reduction
        )
