# Open-data augmentation boundary

The already supplied official FAQ item7 asks: «Можно ли дополнять датасет своими съёмками, синтетикой или открытыми датасетами?» The answer is: «Да, это приветствуется.» The task brief/FAQ permits external open data; it does not grant rights to arbitrary web data or permit sending bank videos, frames, descriptions or per-video outputs to cloud AI.

Before any download or training, verify the actual dataset license and the separate code/weight licenses, commercial compatibility, attribution obligations, relevance, size and local compute budget. A model-card license tag alone is insufficient. No paid compute, cloud inference, face identification or audio processing is allowed.

External training data belongs only in the training pipeline. Bank TUNE/HOLDOUT remain closed for model fitting. Check exact duplicates locally without face identification, preserve provenance, and keep all frames/augmentations of one video in one group. Do not claim generic anomalies or hand boxes are bank violation types.

The parent search found no approved compact cash-handling video set. HaGRIDv2 no_gesture is a possible hand-localization source with a custom license requiring full review, including the chosen weights/runtime; static poses and boxes do not annotate cash-procedure sequences. BankNote-Net has weak transfer to this case because it lacks tenge, temporal labels and boxes. Neither has been adopted or downloaded here. Large or noncommercial corpora are excluded from the current overnight plan.

The selected cheap diagnostic used only already frozen XCLIP TRAIN feature caches: a fixed training-fold hard-negative prototype. It completed once, did not improve the operational gate and was closed; see `xclip-hard-negative.md`. It requested no external data and no new encoder inference. A region experiment should be considered only with a reliable local region definition or a measurable preprocessing-coverage problem; an arbitrary central crop is not a verified cash work area.
