_base_ = [
    '/workdir/configs/mmdetection/detectors_cascade_rcnn_r50_1x_coco.py',
    '/workdir/configs/mmdetection/dataset.py',
]

model = dict(
    backbone=dict(norm_cfg=dict(type='SyncBN', requires_grad=True), norm_eval=False),
    test_cfg=dict(rcnn=dict(score_thr=0.0001)))

optimizer = dict(type='Adam', lr=4e-5)
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))

lr_config = dict(policy='CosineAnnealing', warmup='linear', warmup_iters=1000, warmup_ratio=1.0 / 5, min_lr_ratio=1e-8)
total_epochs = 50

# optimizer = dict(type='SGD', lr=0.007, momentum=0.9, weight_decay=1e-4)
# optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))

# learning policy
# lr_config = dict(policy='step', warmup='linear', warmup_iters=500, gamma=0.2, warmup_ratio=0.001, step=[30, 38])
# total_epochs = 50

evaluation = dict(interval=2, iou_thr=0.4)
log_config = dict(interval=50, hooks=[dict(type='TextLoggerHook'), dict(type='TensorboardLoggerHook')])

fp16 = dict(loss_scale=dict(mode='dynamic'))
custom_hooks = [dict(type='NumClassCheckHook')]

dist_params = dict(backend='nccl')
log_level = 'INFO'
load_from = None
resume_from = None
workflow = [('train', 1)]
checkpoint_config = dict(interval=1)
