# =============================================================================
# Author: Xianyuan Liu, xianyuan.liu@sheffield.ac.uk or xianyuan.liu@outlook.com
#         Haiping Lu, h.lu@sheffield.ac.uk or hplu@ieee.org
# =============================================================================

"""Construct a dataset for videos with (multiple) source and target domains"""

import logging

import numpy as np
from sklearn.utils import check_random_state

from kale.loaddata.multi_domain import DatasetSizeType, MultiDomainDatasets, WeightingType
from kale.loaddata.sampler import FixedSeedSamplingConfig, MultiDataLoader
from kale.loaddata.video_access import get_image_modality


class VideoMultiDomainDatasets(MultiDomainDatasets):
    def __init__(
        self,
        source_access_dict,
        target_access_dict,
        image_modality,
        seed,
        config_weight_type="natural",
        config_size_type=DatasetSizeType.Max,
        val_split_ratio=0.1,
        source_sampling_config=None,
        target_sampling_config=None,
        n_fewshot=None,
        random_state=None,
    ):
        """The class controlling how the source and target domains are iterated over when the input is joint.
            Inherited from MultiDomainDatasets.
        Args:
            source_access_dict (dictionary): dictionary of source RGB and flow dataset accessors
            target_access_dict (dictionary): dictionary of target RGB and flow dataset accessors
            image_modality (string): image type (RGB or Optical Flow)
            seed (int): seed value set manually.
        """

        self._image_modality = image_modality
        self.rgb, self.flow, self.audio = get_image_modality(self._image_modality)
        self._seed = seed

        if self.rgb:
            source_access = source_access_dict["rgb"]
            target_access = target_access_dict["rgb"]
        if self.flow:
            source_access = source_access_dict["flow"]
            target_access = target_access_dict["flow"]
        if self.audio:
            source_access = source_access_dict["audio"]
            target_access = target_access_dict["audio"]

        weight_type = WeightingType(config_weight_type)
        size_type = DatasetSizeType(config_size_type)

        if weight_type is WeightingType.PRESET0:
            self._source_sampling_config = FixedSeedSamplingConfig(
                class_weights=np.arange(source_access.n_classes(), 0, -1)
            )
            self._target_sampling_config = FixedSeedSamplingConfig(
                class_weights=np.random.randint(1, 4, size=target_access.n_classes())
            )
        elif weight_type is WeightingType.BALANCED:
            self._source_sampling_config = FixedSeedSamplingConfig(balance=True)
            self._target_sampling_config = FixedSeedSamplingConfig(balance=True)
        elif weight_type not in WeightingType:
            raise ValueError(f"Unknown weighting method {weight_type}.")
        else:
            self._source_sampling_config = FixedSeedSamplingConfig(seed=self._seed)
            self._target_sampling_config = FixedSeedSamplingConfig(seed=self._seed)

        self._source_access_dict = source_access_dict
        self._target_access_dict = target_access_dict
        self._val_split_ratio = val_split_ratio
        self._rgb_source_by_split = {}
        self._flow_source_by_split = {}
        self._audio_source_by_split = {}
        self._rgb_target_by_split = {}
        self._flow_target_by_split = {}
        self._audio_target_by_split = {}
        self._size_type = size_type
        self._n_fewshot = n_fewshot
        self._random_state = check_random_state(random_state)
        self._source_by_split = {}
        self._labeled_target_by_split = None
        self._target_by_split = {}

    def prepare_data_loaders(self):
        if self.rgb:
            logging.debug("Load RGB train and val")
            (self._rgb_source_by_split["train"], self._rgb_source_by_split["valid"]) = self._source_access_dict[
                "rgb"
            ].get_train_val(self._val_split_ratio)

            (self._rgb_target_by_split["train"], self._rgb_target_by_split["valid"]) = self._target_access_dict[
                "rgb"
            ].get_train_val(self._val_split_ratio)

            logging.debug("Load RGB Test")
            self._rgb_source_by_split["test"] = self._source_access_dict["rgb"].get_test()
            self._rgb_target_by_split["test"] = self._target_access_dict["rgb"].get_test()

        if self.flow:
            logging.debug("Load flow train and val")
            (self._flow_source_by_split["train"], self._flow_source_by_split["valid"]) = self._source_access_dict[
                "flow"
            ].get_train_val(self._val_split_ratio)

            (self._flow_target_by_split["train"], self._flow_target_by_split["valid"]) = self._target_access_dict[
                "flow"
            ].get_train_val(self._val_split_ratio)

            logging.debug("Load flow Test")
            self._flow_source_by_split["test"] = self._source_access_dict["flow"].get_test()
            self._flow_target_by_split["test"] = self._target_access_dict["flow"].get_test()

        if self.audio:
            logging.debug("Load audio train and val")
            (self._audio_source_by_split["train"], self._audio_source_by_split["valid"]) = self._source_access_dict[
                "audio"
            ].get_train_val(self._val_split_ratio)

            (self._audio_target_by_split["train"], self._audio_target_by_split["valid"]) = self._target_access_dict[
                "audio"
            ].get_train_val(self._val_split_ratio)

            logging.debug("Load RGB Test")
            self._audio_source_by_split["test"] = self._source_access_dict["audio"].get_test()
            self._audio_target_by_split["test"] = self._target_access_dict["audio"].get_test()

    def get_domain_loaders(self, split="train", batch_size=32):
        rgb_source_ds = rgb_target_ds = flow_source_ds = flow_target_ds = audio_source_ds = audio_target_ds = None
        rgb_source_loader = rgb_target_loader = flow_source_loader = flow_target_loader = audio_source_loader = audio_target_loader = None
        rgb_target_labeled_loader = flow_target_labeled_loader = audio_target_labeled_loader = None
        rgb_target_unlabeled_loader = flow_target_unlabeled_loader = audio_target_unlabeled_loader = n_dataset = None

        if self.rgb:
            rgb_source_ds = self._rgb_source_by_split[split]
            rgb_source_loader = self._source_sampling_config.create_loader(rgb_source_ds, batch_size)
            rgb_target_ds = self._rgb_target_by_split[split]

        if self.flow:
            flow_source_ds = self._flow_source_by_split[split]
            flow_source_loader = self._source_sampling_config.create_loader(flow_source_ds, batch_size)
            flow_target_ds = self._flow_target_by_split[split]

        if self.audio:
            audio_source_ds = self._audio_source_by_split[split]
            audio_source_loader = self._source_sampling_config.create_loader(audio_source_ds, batch_size)
            audio_target_ds = self._audio_target_by_split[split]

        if self._labeled_target_by_split is None:
            # unsupervised target domain
            if self.rgb:
                n_dataset, target_batch_size = DatasetSizeType.get_size(
                    self._size_type, batch_size, rgb_source_ds, rgb_target_ds
                )
                rgb_target_loader = self._target_sampling_config.create_loader(rgb_target_ds, target_batch_size)
            if self.flow:
                n_dataset, target_batch_size = DatasetSizeType.get_size(
                    self._size_type, batch_size, flow_source_ds, flow_target_ds
                )
                flow_target_loader = self._target_sampling_config.create_loader(flow_target_ds, target_batch_size)
            if self.audio:
                n_dataset, target_batch_size = DatasetSizeType.get_size(
                    self._size_type, batch_size, audio_source_ds, audio_target_ds
                )
                audio_target_loader = self._target_sampling_config.create_loader(audio_target_ds, target_batch_size)

            dataloaders = [rgb_source_loader, flow_source_loader, audio_source_loader, rgb_target_loader, flow_target_loader, audio_target_loader]
            dataloaders = [x for x in dataloaders if x is not None]

            return MultiDataLoader(dataloaders=dataloaders, n_batches=max(n_dataset // batch_size, 1),)
        else:
            # semi-supervised target domain
            if self.rgb:
                rgb_target_labeled_ds = self._labeled_target_by_split[split]
                rgb_target_unlabeled_ds = rgb_target_ds
                # label domain: always balanced
                n_dataset, target_batch_size = DatasetSizeType.get_size(
                    self._size_type, batch_size, rgb_source_ds, rgb_target_labeled_ds, rgb_target_unlabeled_ds
                )
                rgb_target_labeled_loader = FixedSeedSamplingConfig(balance=True, class_weights=None).create_loader(
                    rgb_target_labeled_ds, batch_size=min(len(rgb_target_labeled_ds), batch_size)
                )

                rgb_target_unlabeled_loader = self._target_sampling_config.create_loader(
                    rgb_target_unlabeled_ds, batch_size
                )

            if self.flow:
                flow_target_labeled_ds = self._labeled_target_by_split[split]
                flow_target_unlabeled_ds = flow_target_ds
                n_dataset, _ = DatasetSizeType.get_size(
                    self._size_type, batch_size, flow_source_ds, flow_target_labeled_ds, flow_target_unlabeled_ds
                )
                flow_target_labeled_loader = FixedSeedSamplingConfig(balance=True, class_weights=None).create_loader(
                    flow_target_labeled_ds, batch_size=min(len(flow_target_labeled_ds), batch_size)
                )
                flow_target_unlabeled_loader = self._target_sampling_config.create_loader(
                    flow_target_unlabeled_ds, batch_size
                )

            if self.audio:
                audio_target_labeled_ds = self._labeled_target_by_split[split]
                audio_target_unlabeled_ds = audio_target_ds
                # label domain: always balanced
                n_dataset, target_batch_size = DatasetSizeType.get_size(
                    self._size_type, batch_size, audio_source_ds, audio_target_labeled_ds, audio_target_unlabeled_ds
                )
                audio_target_labeled_loader = FixedSeedSamplingConfig(balance=True, class_weights=None).create_loader(
                    audio_target_labeled_ds, batch_size=min(len(audio_target_labeled_ds), batch_size)
                )

                audio_target_unlabeled_loader = self._target_sampling_config.create_loader(
                    audio_target_unlabeled_ds, batch_size
                )

            # combine loaders into a list and remove the loader which is NONE.
            dataloaders = [
                rgb_source_loader,
                flow_source_loader,
                audio_source_loader,
                rgb_target_labeled_loader,
                flow_target_labeled_loader,
                audio_target_labeled_loader,
                rgb_target_unlabeled_loader,
                flow_target_unlabeled_loader,
                audio_target_unlabeled_loader,
            ]
            dataloaders = [x for x in dataloaders if x is not None]

            return MultiDataLoader(dataloaders=dataloaders, n_batches=max(n_dataset // batch_size, 1))

    def __len__(self):
        if self.rgb:
            source_ds = self._rgb_source_by_split["train"]
            target_ds = self._rgb_target_by_split["train"]
        if self.flow:
            source_ds = self._flow_source_by_split["train"]
            target_ds = self._flow_target_by_split["train"]
        if self.audio:
            source_ds = self._audio_source_by_split["train"]
            target_ds = self._audio_target_by_split["train"]

        if self._labeled_target_by_split is None:
            return DatasetSizeType.get_size(self._size_type, source_ds, target_ds)
        else:
            labeled_target_ds = self._labeled_target_by_split["train"]
            return DatasetSizeType.get_size(self._size_type, source_ds, labeled_target_ds, target_ds)
