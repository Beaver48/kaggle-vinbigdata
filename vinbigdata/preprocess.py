import glob
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from albumentations import BboxParams, Compose, Resize
from pascal_voc_writer import Writer
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import apply_voi_lut
from typing_extensions import TypedDict
from vinbigdata import BoxCoordsFloat, BoxCoordsInt, classname2mmdetid
from vinbigdata.utils import abs2rel

ImageMeta = TypedDict(
    'ImageMeta', {
        'image_id': str,
        'class_name': str,
        'rad_id': Optional[str],
        'x_min': float,
        'y_min': float,
        'x_max': float,
        'y_max': float
    })


class BaseTransform(ABC):
    """ Base transformation
    """

    def __init__(self, fized_size: Tuple[int, int]) -> None:
        self.resize_transform = Compose([Resize(fized_size[0], fized_size[0], always_apply=True)],
                                        bbox_params=BboxParams(
                                            format='pascal_voc', min_visibility=0.0, label_fields=['classes']))

    @abstractmethod
    def __call__(self, img_name: str, img: np.array, bboxes: List[BoxCoordsInt],
                 classes: List[str]) -> Tuple[np.array, List[BoxCoordsInt], List[str]]:
        raise NotImplementedError('call method not implemented')


class GrayscaleTransform(BaseTransform):
    """ Transformation for grayscale
    """

    def __init__(self, fized_size: Tuple[int, int] = (1024, 1024)) -> None:
        super(GrayscaleTransform, self).__init__(fized_size)

    def __call__(self, img_name: str, img: np.array, bboxes: List[BoxCoordsInt],
                 classes: List[str]) -> Tuple[np.array, List[BoxCoordsInt], List[str]]:
        assert len(img.shape) == 2
        res = self.resize_transform(image=cv2.cvtColor(img, cv2.COLOR_GRAY2RGB), bboxes=bboxes, classes=classes)
        return (res['image'], res['bboxes'], res['classes'])


class MaskTransform(BaseTransform):
    """ Transformation for grayscale
    """

    def __init__(self, mask_path: str, fized_size: Tuple[int, int] = (1024, 1024)) -> None:
        super(MaskTransform, self).__init__(fized_size)
        self.masks = {Path(mask).name: mask for mask in glob.glob(mask_path + '/*')}

    def __call__(self, img_name: str, img: np.array, bboxes: List[BoxCoordsInt],
                 classes: List[str]) -> Tuple[np.array, List[BoxCoordsInt], List[str]]:
        mask = cv2.resize(
            cv2.imread(self.masks[Path(img_name).name]), (img.shape[1], img.shape[0]),
            interpolation=cv2.INTER_LANCZOS4)[:, :, 0]
        assert len(mask.shape) == 2
        img = np.concatenate([img[:, :, np.newaxis], img[:, :, np.newaxis], mask[:, :, np.newaxis]], axis=2)
        res = self.resize_transform(image=img, bboxes=bboxes, classes=classes)
        assert len(img.shape) == 3
        return (res['image'], res['bboxes'], res['classes'])


class EqualizeTransform(BaseTransform):
    """ Transformation with equalization
    """

    def __init__(
        self,
        clahe_clip_limit: float = 4.0,
        clahe_grid: Tuple[int, int] = (8, 8),
        fized_size: Tuple[int, int] = (1024, 1024)
    ) -> None:
        super(EqualizeTransform, self).__init__(fized_size)
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_grid = clahe_grid

    def __call__(self, img_name: str, img: np.array, bboxes: List[BoxCoordsInt],
                 classes: List[str]) -> Tuple[np.array, List[BoxCoordsInt], List[str]]:
        assert len(img.shape) == 2
        clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=self.clahe_grid)
        img = np.concatenate(
            [img[:, :, np.newaxis],
             cv2.equalizeHist(img)[:, :, np.newaxis],
             clahe.apply(img)[:, :, np.newaxis]],
            axis=2)
        res = self.resize_transform(image=img, bboxes=bboxes, classes=classes)
        return res['image'], res['bboxes'], res['classes']


class BaseWriter(ABC):
    """ Base class for writers
    """

    def __init__(self, directory: str, clear: bool, image_prepocessor: BaseTransform) -> None:
        self.image_prepocessor = image_prepocessor
        self.annotations_dir, self.images_dir, self.image_sets_dir = self._create_dirs(directory, clear=clear)

    @abstractmethod
    def process_image(
            self,
            img_name: str,
            img: np.array,
            bboxes: List[BoxCoordsInt],
            classes: List[str],
    ) -> Tuple[int, int]:
        raise NotImplementedError()

    @abstractmethod
    def write_image_set(self, ids: List[str], file_name: str) -> None:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def _create_dirs(data_dir: str, clear: bool = False) -> Tuple[Path, Path, Path]:
        raise NotImplementedError()


class VocWriter(BaseWriter):
    """ Class for writing data in PASCALVOC 2012 format
    """

    def process_image(
            self,
            img_name: str,
            img: np.array,
            bboxes: List[BoxCoordsInt],
            classes: List[str],
    ) -> Tuple[int, int]:
        image_path = self.images_dir / img_name
        xml_path = self.annotations_dir / img_name.replace('.jpg', '.xml').replace('.png', '.xml')
        img, bboxes, classes = self.image_prepocessor(image_path.name, img, bboxes, classes)
        if not (self.images_dir / img_name).exists():
            cv2.imwrite(str(self.images_dir / img_name), img)
        self.write_xml(xml_path, image_path, bboxes, classes, img.shape[0:2])
        return img.shape

    @staticmethod
    def write_xml(xml_path: Path, image_path: Path, bboxes: List[BoxCoordsInt], classes: List[str],
                  img_shape: Tuple[int, int]) -> None:
        writer = Writer(image_path, img_shape[1], img_shape[0])
        if bboxes is not None:
            for bbox, class_name in zip(bboxes, classes):
                if bbox[3] > img_shape[0] or bbox[1] > img_shape[1]:
                    continue
                writer.addObject(class_name, int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        writer.save(xml_path)

    @staticmethod
    def _create_dirs(data_dir: str, clear: bool = False) -> Tuple[Path, Path, Path]:
        base_dir = Path(data_dir)
        if clear and base_dir.exists():
            shutil.rmtree(base_dir)
        annotations = base_dir / 'Annotations'
        images = base_dir / 'JPEGImages'
        image_sets = base_dir / 'image_sets'

        annotations.mkdir(parents=True, exist_ok=True)
        images.mkdir(parents=True, exist_ok=True)
        image_sets.mkdir(parents=True, exist_ok=True)
        return (annotations, images, image_sets)

    def write_image_set(self, ids: List[str], file_name: str) -> None:
        with open(self.image_sets_dir / file_name, 'w') as writer:
            writer.write('\n'.join(ids))


class ScaledYoloWriter(BaseWriter):
    """ Class for writing data in ScaledYolo format
    """

    def process_image(
            self,
            img_name: str,
            img: np.array,
            bboxes: List[BoxCoordsInt],
            classes: List[str],
    ) -> Tuple[int, int]:
        image_path = self.images_dir / img_name
        ann_path = self.annotations_dir / img_name.replace('.jpg', '.txt').replace('.png', '.txt')
        img, bboxes, classes = self.image_prepocessor(image_path.name, img, bboxes, classes)
        if not (self.images_dir / img_name).exists():
            cv2.imwrite(str(self.images_dir / img_name), img)
        self.write_ann(ann_path, bboxes, classes, img.shape[0:2])
        return img.shape

    @staticmethod
    def write_ann(ann_path: Path, bboxes: List[BoxCoordsInt], classes: List[str], img_shape: Tuple[int, int]) -> None:
        class_ids = [classname2mmdetid[cls] for cls in classes]
        normalized_boxes = [abs2rel(box, img_shape) for box in bboxes]
        normalized_boxes = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, box[2] - box[0], box[3] - box[1])
                            for box in normalized_boxes]
        with open(ann_path, 'w') as writer:
            for bbox, class_id in zip(normalized_boxes, class_ids):
                writer.write(' '.join([str(class_id)] + [str(coord) for coord in bbox]) + '\n')

    @staticmethod
    def _create_dirs(data_dir: str, clear: bool = False) -> Tuple[Path, Path, Path]:
        base_dir = Path(data_dir)
        if clear and base_dir.exists():
            shutil.rmtree(base_dir)
        annotations = base_dir / 'labels'
        images = base_dir / 'JPEGImages'
        image_sets = base_dir / 'yolo_image_sets'

        annotations.mkdir(parents=True, exist_ok=True)
        images.mkdir(parents=True, exist_ok=True)
        image_sets.mkdir(parents=True, exist_ok=True)
        return (annotations, images, image_sets)

    def write_image_set(self, ids: List[str], file_name: str) -> None:
        with open(self.image_sets_dir / file_name, 'w') as writer:
            writer.write('\n'.join([str(self.images_dir / (id + '.png')) for id in ids]))


def read_dicom_img(path: str, apply_voi: bool = True) -> np.array:
    dicom_data = dcmread(path)
    if apply_voi:
        img_data = apply_voi_lut(dicom_data.pixel_array, dicom_data)
    else:
        img_data = dicom_data.pixel_array

    if dicom_data.PhotometricInterpretation == 'MONOCHROME1':
        img_data = np.amax(img_data) - img_data
    img_data = img_data - np.min(img_data)
    img_data = img_data / np.max(img_data)
    img_data = (img_data * 256).astype(np.uint8)
    return img_data


def convert_bboxmeta2arrays(bbox_metas: List[ImageMeta]) -> Tuple[List[BoxCoordsFloat], List[float], List[str]]:
    bboxes = [(bbox_meta['x_min'], bbox_meta['y_min'], bbox_meta['x_max'], bbox_meta['y_max'])
              for bbox_meta in bbox_metas if bbox_meta['class_name'] != 'No finding']
    labels = [bbox_meta['class_name'] for bbox_meta in bbox_metas if bbox_meta['class_name'] != 'No finding']
    scores = [1.0 for _ in range(len(bboxes))]
    return (bboxes, scores, labels)
