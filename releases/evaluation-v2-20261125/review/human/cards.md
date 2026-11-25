# Evaluation candidate review cards

Evaluator-only material. AI-prepared mechanical checks; every human decision remains PENDING.
Do not paste this packet, truth labels or future events into the application agents or prompt-tuning sessions.
Read PRIORITY_5_REVIEW.md for review, revision and release instructions.

## EVAL2-001 — equipment_only

Input hash: `d44a46de7d32411dd72253eaf4243e27054744966517428d923b11c3beda153f`.
Truth hash: `c0d2939557928bd15aef5aa9c4a7154a8a535fea029a34b594cc32aa65c1af4e`.
Topology: {"depth_counts": {"1": 1, "2": 3, "3": 3, "4": 5, "5": 3}, "non_root_branch_degrees": [1, 1, 1, 2, 3, 3, 3], "roads_all_depot_spokes": false, "root_children": 1, "sites": 15}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S01:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-001`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-002 — equipment_only

Input hash: `7f95d03c9d3937039144bae6b401492a9952b529ff1e3867b03ef81130183e06`.
Truth hash: `f03ae65e71605319c0e176d8780d83281ae22c283d63b55f40617d33fc4669d4`.
Topology: {"depth_counts": {"1": 2, "2": 1, "3": 2, "4": 2, "5": 2, "6": 1, "7": 2, "8": 3, "9": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 2, 2, 2, 2, 2], "roads_all_depot_spokes": false, "root_children": 2, "sites": 16}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S16:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-002`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-003 — power_only

Input hash: `811ccf82d7a531ee00a0605b4479c4b3ea1c90a4b6a7a4e22684a022a1249494`.
Truth hash: `43048df39725c59ea26f2b923f626036d79fcbd772e953227d172d80c732843f`.
Topology: {"depth_counts": {"1": 2, "2": 3, "3": 4, "4": 3, "5": 2, "6": 2, "7": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 2, 2, 2, 2, 3], "roads_all_depot_spokes": false, "root_children": 2, "sites": 17}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S05:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-003`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-004 — power_only

Input hash: `7fbf0e01686d145c06756db686602b72e79b56e05995d72e0e7aa026c7324e69`.
Truth hash: `c3b4aba50d12595fd32d6c1b41b038a0f5c4ebd106dd6f3cf9ad6456460b15cb`.
Topology: {"depth_counts": {"1": 1, "2": 3, "3": 1, "4": 2, "5": 4, "6": 4, "7": 3}, "non_root_branch_degrees": [1, 1, 1, 1, 2, 2, 3, 3, 3], "roads_all_depot_spokes": false, "root_children": 1, "sites": 18}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S18:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-004`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-005 — power_and_backhaul

Input hash: `9037dea830efb5e826051077d5c5898f2bd2854949d2986f0861867ed2cb72a4`.
Truth hash: `733ea801dd1513d6dc67eb110bd7f7b4f7ffc35dad054fe3adcd585e3204c65d`.
Topology: {"depth_counts": {"1": 1, "2": 2, "3": 2, "4": 1, "5": 2, "6": 5, "7": 3, "8": 2, "9": 1}, "non_root_branch_degrees": [1, 1, 1, 2, 2, 2, 2, 3, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 19}.
Shape matches development: False; exact report wording overlap: 0/3.
Mechanical unresolved fields: link:L07, site:S01:grid_power_ok, site:S07:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-005`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-006 — power_and_backhaul

Input hash: `ff7dcf81244df3daafc7cd9ce9b19781e82d564b11162ff0727a3a429c4e25dc`.
Truth hash: `fb850f722b820799263305a6c0fda324f1b764fc2b8029d3ee97a3b1de42120a`.
Topology: {"depth_counts": {"1": 2, "2": 3, "3": 1, "4": 3, "5": 4, "6": 2, "7": 2, "8": 3}, "non_root_branch_degrees": [1, 1, 1, 2, 2, 2, 3, 3, 3], "roads_all_depot_spokes": false, "root_children": 2, "sites": 20}.
Shape matches development: False; exact report wording overlap: 0/3.
Mechanical unresolved fields: link:L20, site:S01:grid_power_ok, site:S20:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-006`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-007 — skill_shortage

Input hash: `9d2931ae2ac99685428ad514200bf343e5e25cbe04d37bbdafe98e71089a9bc3`.
Truth hash: `66dda5e685dcf8882cf5ff32d29f83497c38c7fb1f4304213a302db3817981be`.
Topology: {"depth_counts": {"1": 2, "2": 2, "3": 1, "4": 1, "5": 2, "6": 3, "7": 1, "8": 1, "9": 2}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 2, 2, 2, 2], "roads_all_depot_spokes": false, "root_children": 2, "sites": 15}.
Shape matches development: False; exact report wording overlap: 0/3.
Mechanical unresolved fields: link:L09, site:S01:grid_power_ok, site:S09:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-007`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-008 — skill_shortage

Input hash: `a07bb92c6b1e2fd65d447fcd2e1b1bed86e3eb34161e8162a0ab5ae4ff97f184`.
Truth hash: `e166e9ac03264ef9a94311e8cca30bad7724a0ca111b8cdc06af59e6cc5bfe29`.
Topology: {"depth_counts": {"1": 1, "2": 2, "3": 7, "4": 4, "5": 1, "6": 1}, "non_root_branch_degrees": [1, 1, 1, 2, 3, 7], "roads_all_depot_spokes": false, "root_children": 1, "sites": 16}.
Shape matches development: False; exact report wording overlap: 0/3.
Mechanical unresolved fields: link:L16, site:S01:grid_power_ok, site:S16:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-008`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-009 — route_closure

Input hash: `204c2a09c8c060da4c3c37b5da432253ff7cc03bec888e76d464b2b5faef506b`.
Truth hash: `c93b14ad464dbeec5bde9e8a351364120182cb00546681a5ee5a018c0736f172`.
Topology: {"depth_counts": {"1": 3, "2": 4, "3": 5, "4": 4, "5": 1}, "non_root_branch_degrees": [1, 1, 2, 2, 2, 2, 4], "roads_all_depot_spokes": false, "root_children": 3, "sites": 17}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: road:R17, site:S17:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-009`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-010 — route_closure

Input hash: `fb205ef30d2c863a3af41a2e479cfa3e39c2de6e2871fd4caf4a2430efeb0e24`.
Truth hash: `5b2adfa8ca416e47a32efdee08517095f499fec887816b1695db002fbb0928c1`.
Topology: {"depth_counts": {"1": 2, "2": 2, "3": 3, "4": 4, "5": 3, "6": 4}, "non_root_branch_degrees": [1, 1, 2, 2, 2, 2, 3, 3], "roads_all_depot_spokes": false, "root_children": 2, "sites": 18}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: road:R18, site:S18:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-010`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-011 — conflicting_reports

Input hash: `ec52294a04b4da2255d98337fb2eec004bb4b66c7b76cded75b7de42171ff21c`.
Truth hash: `d214cf6eac7cead33b546cbeaa7884505370085f8b0c32b81fc62d8ce25f8fcb`.
Topology: {"depth_counts": {"1": 1, "2": 2, "3": 4, "4": 5, "5": 5, "6": 1, "7": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 19}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S03:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-011`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-012 — conflicting_reports

Input hash: `a4b0462e99859a15f356b753911b4eeefe6d80f31054a96f974d7c8a6024ed56`.
Truth hash: `38c19262b22d75230ca76457bbb2d3369b108b7240d3519e19bebbde3b710976`.
Topology: {"depth_counts": {"1": 2, "2": 4, "3": 4, "4": 3, "5": 1, "6": 3, "7": 2, "8": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3], "roads_all_depot_spokes": false, "root_children": 2, "sites": 20}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S20:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-012`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-013 — stale_reports

Input hash: `6687373d8bb74ba9f352abb53368a24d4ebb16728877317deaf14bc291c1b402`.
Truth hash: `90d4136015fd48fc8533d96cd004e5ff8f7d9b6dbc9b09233f961ee6c132d099`.
Topology: {"depth_counts": {"1": 2, "2": 2, "3": 1, "4": 2, "5": 1, "6": 2, "7": 2, "8": 2, "9": 1}, "non_root_branch_degrees": [1, 1, 1, 2, 2, 2, 2, 2], "roads_all_depot_spokes": false, "root_children": 2, "sites": 15}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S04:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-013`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-014 — stale_reports

Input hash: `5d47d646afcd2bade07bcbef70bfadba4be32800f6c4e331e4d2df67f790bcaa`.
Truth hash: `20f8c311f713b6939288b45581a51f9f457326b8204e0a2c5e5c4b2d62365027`.
Topology: {"depth_counts": {"1": 2, "2": 1, "3": 1, "4": 2, "5": 2, "6": 2, "7": 2, "8": 3, "9": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 2, 2, 2, 2], "roads_all_depot_spokes": false, "root_children": 2, "sites": 16}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S16:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-014`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-015 — missing_critical_evidence

Input hash: `7fce22312021e9edb9d3a80e5323e6cf8c44bd8d6d4115a1a14f55aeb6642f56`.
Truth hash: `604809bb35a6069666601bcb550ac2b52daf7cafbd2dbc17203a83d711a86a01`.
Topology: {"depth_counts": {"1": 1, "2": 1, "3": 4, "4": 7, "5": 4}, "non_root_branch_degrees": [1, 1, 1, 2, 2, 2, 3, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 17}.
Shape matches development: False; exact report wording overlap: 0/0.
Mechanical unresolved fields: site:S01:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-015`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-016 — missing_critical_evidence

Input hash: `16fab58b6b08fd7bbfe097e288aff111e1bf29790eea6ed88c5d002e0f761ffe`.
Truth hash: `5d74decdf0e009397f0593b8e9b0d657826d575964795830a2189baa03052e61`.
Topology: {"depth_counts": {"1": 1, "2": 4, "3": 2, "4": 5, "5": 3, "6": 2, "7": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 2, 2, 2, 3, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 18}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S18:equipment_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-016`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-017 — generator_exhaustion

Input hash: `ccef7697544abed8d3f3515097a18b3469682d038ecff2c9d89ce907badffe0a`.
Truth hash: `c79b2d5dc2ece904a8409dd85e6eccc6b6d33b1840240e80ed9389ff53294faf`.
Topology: {"depth_counts": {"1": 1, "2": 1, "3": 2, "4": 4, "5": 4, "6": 4, "7": 2, "8": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 19}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S05:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-017`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-018 — generator_exhaustion

Input hash: `e819463e4bb784e09ce569811f6caa986cdc2fcf14e92f629aadb3116bf096c6`.
Truth hash: `46b8857c3aa346d09ff73eccae28a375d5459826abae2d0c1c93ced1c4499310`.
Topology: {"depth_counts": {"1": 5, "2": 5, "3": 4, "4": 3, "5": 1, "6": 2}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 1, 2, 3, 3], "roads_all_depot_spokes": false, "root_children": 5, "sites": 20}.
Shape matches development: False; exact report wording overlap: 0/1.
Mechanical unresolved fields: site:S20:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-018`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-019 — resource_loss_replanning

Input hash: `39acc40f5ae2a9baf945feaa67be06a038f5a181856471bc31b0ac133e41f711`.
Truth hash: `0f77beea81f768acc2f517af1f24f799de5e54a8c876c2a13aa51a5aea69245f`.
Topology: {"depth_counts": {"1": 1, "2": 2, "3": 3, "4": 1, "5": 1, "6": 4, "7": 2, "8": 1}, "non_root_branch_degrees": [1, 1, 1, 1, 2, 2, 2, 4], "roads_all_depot_spokes": false, "root_children": 1, "sites": 15}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S01:equipment_ok, site:S07:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-019`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.

## EVAL2-020 — resource_loss_replanning

Input hash: `5ff09be5b5ea453727d517e61cdfdf3e58d549a41284a3b25bf6c706c65633ff`.
Truth hash: `8190b026c1f40f475835a435b10b5bae54b6cb05ede6a2675e3907ad047e3943`.
Topology: {"depth_counts": {"1": 1, "2": 1, "3": 3, "4": 1, "5": 1, "6": 1, "7": 2, "8": 2, "9": 2, "10": 2}, "non_root_branch_degrees": [1, 1, 1, 1, 1, 1, 2, 2, 2, 3], "roads_all_depot_spokes": false, "root_children": 1, "sites": 16}.
Shape matches development: False; exact report wording overlap: 0/2.
Mechanical unresolved fields: site:S01:equipment_ok, site:S16:grid_power_ok. This is not a gold optimum.
Resources, labels, missing-fact labels and evaluator events: [packet.json](packet.json), case `EVAL2-020`.
Human tasks: inspect the input/raw/truth files listed in the packet; check every label and timing; independently reason through outcomes; revise or justify diversity limits; record actual reviewer/UTC date and declarations in reviews.csv.
