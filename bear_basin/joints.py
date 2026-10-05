"""Manual assembly schedule, independent of Blender scene mutation."""


def build_joints(geometry):
    M = geometry.members
    NET_FIX = geometry.net_fixings
    J = []  # (step, attached_member, base_member, fastener, count)

    def j(step, a, b, ft, n):
        J.append((step, a, b, ft, n))

    for leg, n in (("C01A", 2), ("C04A", 2), ("C02", 2)):
        j(14, "S04A", leg, "M896", n)
    for leg, n in (("C01A", 2), ("C04A", 1), ("C02", 2)):
        j(15, "K07", leg, "M8107", n)
    for leg, n in (("C01B", 2), ("C04B", 2), ("C03", 2)):
        j(23, "S04", leg, "M896", n)
    for leg, n in (("C01B", 2), ("C04B", 1), ("C03", 2)):
        j(24, "K06", leg, "M8107", n)
    j(29, "K08_W", "C02", "M8107", 1)
    j(29, "K08_W", "C01B", "M8107", 1)
    j(30, "K08_E", "C03", "M8107", 1)
    j(30, "K08_E", "C01A", "M8107", 1)
    j(31, "S03_E", "C03", "M896", 2)
    j(31, "S03_E", "C01A", "M896", 2)
    j(32, "S03_W", "C02", "M896", 2)
    j(32, "S03_W", "C01B", "M896", 2)
    j(33, "C06", "K08_E", "M8107", 1)
    j(33, "C06", "S03_E", "M896", 2)
    j(34, "C05", "K08_W", "M8107", 1)
    j(34, "C05", "S03_W", "M896", 2)
    for n, leg in (
        ("FA17_C03", "C03"),
        ("FA17_C01B", "C01B"),
        ("FA17_C02", "C02"),
        ("FA17_C01A", "C01A"),
        ("FA17_C01A_y", "C01A"),
        ("FA17_C06", "C06"),
    ):
        j(35, n, leg, "SW50", 2)
    for leg in ("C01A", "C02", "C03", "C01B"):
        for ax, rail in (
            ("x", "K07" if leg in ("C01A", "C02") else "K06"),
            ("y", "K08_E" if leg in ("C01A", "C03") else "K08_W"),
        ):
            j(42, f"KA13_{leg}_{ax}", rail, "M865", 1)
            j(42, f"KA13_{leg}_{ax}", leg, "M8SW50", 1)
    j(46, "KA11_C", "C05", "SW75", 2)
    j(46, "KA11_C", "C06", "SW75", 2)
    for side in ("W", "E"):
        for fb in ("F", "B"):
            j(
                47, f"K08_{side}", f"C11_{side}_{fb}", "M8107", 2
            )  # bolts from outside the rail into T-nuts in the brace
    for fb in ("F", "B"):
        j(49, f"C11_W_{fb}", f"K05_{fb}", "M8107", 1)
        j(49, f"C11_E_{fb}", f"K05_{fb}", "M8107", 1)
        j(53, f"KA11_{fb}", "K08_W", "SW75", 2)
        j(53, f"KA11_{fb}", "K08_E", "SW75", 2)
    for i in range(2):
        for fb in ("F", "B"):
            j(51, f"CA10_{i}_{fb}", f"K05_{fb}", "M8107", 2)
    table_rows = sorted(
        (name for name, part in M.items() if part["code"] == "W01"),
        key=lambda name: M[name]["p0"].x,
    )
    # Floorboard hardware follows the drawings in steps 62-74.
    for name, d in M.items():
        code = d["code"]
        if code not in ("W09", "W11", "W10", "W02", "W01", "W13"):
            continue
        if code == "W01":
            i = table_rows.index(name)
            step = 65 if i == 0 else 70
            j(step, name, "KA11_C", "SW35", 1)
            for end in ("F", "B"):
                j(step, name, f"CA10_{i}_{end}", "SW35", 1)
        elif code == "W02":
            table_index = 0 if d["p0"].x < 0 else 1
            step = 66 if table_index == 0 else 71
            front = d["p0"].y < 0
            for support in (
                ("K06", "K05_F", "KA11_F") if front else ("K07", "K05_B", "KA11_B")
            ):
                j(step, name, support, "SW35", 1)
        elif code == "W13":
            west, front = d["p0"].x < 0, d["p1"].y < 0
            block = {
                (True, True): "FA17_C01B",
                (True, False): "FA17_C02",
                (False, True): "FA17_C03",
                (False, False): "FA17_C01A",
            }[(west, front)]
            step = 63 if west else 74
            j(step, name, "K08_W" if west else "K08_E", "SW35", 3)
            j(step, name, block, "SW35", 3)
        else:
            step = 67 if code == "W10" else 62 if code == "W11" else 64
            for support in ("K06", "K05_F", "K05_B", "K07"):
                count = 1 if code == "W10" and support in ("K06", "K07") else 2
                j(step, name, support, "SW35", count)
    j(55, "F04_E", "C06", "SW60", 2)
    j(55, "F04_E", "C01A", "SW60", 2)
    for rail, legs in (
        ("F09_B", ("C01A", "C04A", "C02")),
        ("F09_W", ("C02", "C05", "C01B")),
        ("F09_F", ("C01B", "C04B", "C03")),
        ("FA15_F", ("C01B", "C04B", "C03")),
        ("FA15_W", ("C02", "C05", "C01B")),
        ("S05", ("C02", "C05", "C01B")),
    ):
        for leg in legs:
            j(56, rail, leg, "SW60", 2)
    j(164, "FA13_B", "C01A", "SW60", 2)
    j(164, "FA13_B", "C04A", "SW60", 2)
    j(165, "FA13_E", "C01A", "SW60", 2)
    j(165, "FA13_E", "C06", "SW60", 2)
    j(59, "F13", "C06", "SW60", 2)
    j(59, "F13", "C01A", "SW60", 2)
    for rail, legs in (
        ("F11_B", ("C02", "C04A", "C01A")),
        ("F11_W", ("C02", "C05", "C01B")),
        ("F12", ("C01B", "C04B", "C03")),
    ):
        for leg in legs:
            j(61, rail, leg, "SW60", 2)
    for (
        name,
        d,
    ) in M.items():  # wall boards: 4 SW35 each (2 top, 2 bottom), steps 168-171, 99
        if d["code"] == "W07":
            tag = name.split("_")[1]
            top = {"B": "F09_B", "E": "F04_E", "F": "F09_F", "W": "F09_W"}[tag]
            bot = {"B": "FA13_B", "E": "FA13_E", "F": "FA15_F", "W": "FA15_W"}[tag]
            j(168, name, top, "SW35", 2)
            j(168, name, bot, "SW35", 2)
        if d["code"] == "W14":
            j(99, name, "F07", "SW35", 2)
            j(99, name, "FA14", "SW35", 2)
    for h_, leg, st in (
        ("Handle_C04A", "C04A", 186),
        ("Handle_C02", "C02", 186),
        ("Handle_C08", "C08", 101),
    ):
        j(st, f"{h_}_foot0", leg, "M6SW35", 1)
        j(st, f"{h_}_foot1", leg, "M6SW35", 1)
    # roof (steps 110-139)
    for rail, legs in (
        ("F16_B", ("C09_BW", "C10_B", "C09_BE")),
        ("F16_F", ("C09_FW", "C10_F", "C09_FE")),
        ("F16_W", ("C09_FW", "C10_W", "C09_BW")),
        ("F16_E", ("C09_FE", "C10_E", "C09_BE")),
        ("F14_B", ("C09_BW", "C10_B", "C09_BE")),
        ("F14_F", ("C09_FW", "C10_F", "C09_FE")),
        ("F14_W", ("C09_FW", "C10_W", "C09_BW")),
        ("F15_E", ("C10_E", "C09_BE")),
    ):
        for leg in legs:
            j(110, rail, leg, "M8SW50", 2)
    for cb, legs in (
        ("F13r", ("C10_E", "C09_BE")),
        ("F11r_B", ("C09_BW", "C10_B", "C09_BE")),
        ("F11r_W", ("C09_FW", "C10_W", "C09_BW")),
        ("F12r", ("C09_FW", "C10_F", "C09_FE")),
    ):
        for leg in legs:
            j(120, cb, leg, "SW60", 2)
    for r in ("KA12_BE", "KA12_BW", "KA12_FE", "KA12_FW"):
        j(125, r, "C09_" + r.split("_")[1], "SW60", 2)
        j(126, r, "KA09", "SW60", 1)
    j(136, "F13r", "F13", "M833", 2)
    j(137, "F12r", "F12", "M833", 4)
    j(138, "F11r_B", "F11_B", "M833", 4)
    j(139, "F11r_W", "F11_W", "M833", 4)
    # Tarp assembly, steps 131-133; compass-to-step mapping is not specified.
    for side in ("B", "F", "W", "E"):
        j(131, "Tarp", f"F16_{side}", "SW16", 6)
    # picnic table
    for i in range(2):
        j(141, f"F03_{i}", f"CA10_{i}_F", "M8SW50", 2)
        j(141, f"F03_{i}", f"CA10_{i}_B", "M8SW50", 2)
        j(141, f"F01_{i}", f"CA10_{i}_F", "SW60", 2)
        j(141, f"F01_{i}", f"CA10_{i}_B", "SW60", 2)
    for name in M:
        if name.startswith("Bench_"):
            j(143, name, "F03_0", "SW50", 2)
            j(143, name, "F03_1", "SW50", 2)
        if name.startswith("W05_"):
            j(145, name, "F01_0", "SW35", 2)
            j(145, name, "F01_1", "SW35", 2)
    # small deck
    j(79, "S02", "C07", "M896", 2)
    j(79, "S02", "C08", "M896", 2)
    j(81, "K02_O", "C07", "M8107", 1)
    j(81, "K02_O", "C08", "M8107", 1)
    j(82, "F07", "C07", "M6SW55", 2)
    j(82, "F07", "C08", "M6SW55", 2)
    j(86, "K01", "C03", "M8107", 2)
    j(86, "K01", "C07", "M8107", 2)
    j(87, "K03", "C08", "M8107", 2)
    j(87, "K03", "C06", "M8107", 2)
    for tag, tl, sl in (("F", "C03", "C07"), ("B", "C06", "C08")):
        j(88, f"F05_low_{tag}", tl, "SW60", 2)
        j(88, f"F05_low_{tag}", sl, "SW60", 2)
        j(89, f"F05_top_{tag}", tl, "M6SW55", 2)
        j(89, f"F05_top_{tag}", sl, "M6SW55", 2)
    j(90, "K02_T", "C03", "M8107", 1)
    j(90, "K02_T", "C06", "M8107", 1)
    j(91, "KA10", "K01", "SW75", 2)
    j(91, "KA10", "K03", "SW75", 2)
    j(92, "FA17_C07", "C07", "SW50", 2)
    j(92, "FA17_C08", "C08", "SW50", 2)
    for name, d in M.items():
        if name.endswith(tuple(f"_sd{i}" for i in range(12))):
            j(93, name, "K02_T", "SW35", 2)
            j(93, name, "KA10", "SW35", 2 if d["code"] in ("W12A", "W12") else 1)
            j(93, name, "K02_O", "SW35", 2)
    j(98, "FA14", "C07", "SW60", 2)
    j(98, "FA14", "C08", "SW60", 2)
    j(100, "KA14", "C06", "SW75", 2)
    j(100, "KA14", "C03", "SW75", 2)
    j(172, "Slide", "W12A_sd0", "SW50", 2)
    for k in range(4):
        j(104, "K20", f"F23_{k}", "SW50", 2)
        j(104, "K21", f"F23_{k}", "SW50", 2)
    j(105, "W23", "K20", "SW50", 2)
    j(105, "W23", "K21", "SW50", 2)
    j(106, "K20", "K03", "M8SW60", 1)
    j(106, "K21", "K03", "M8SW60", 1)
    j(190, "Stake_K20", "K20", "SW35", 1)
    # swing frame
    j(148, "DRB01_Ybracket", "C20_F", "M6SW35", 1)
    j(148, "DRB01_Ybracket", "C20_B", "M6SW35", 1)
    j(149, "DRB01_Ybracket", "C20_F", "M6SW35", 1)
    j(149, "DRB01_Ybracket", "C20_B", "M6SW35", 1)
    j(150, "F30", "C20_F", "SW60", 2)
    j(150, "F30", "C20_B", "SW60", 2)
    j(151, "DRB02_Ibracket", "B03", "M6SW35", 2)
    j(152, "DRB02_Ibracket", "B03", "M6SW35", 2)
    j(154, "DRB01_Ybracket", "B03", "M6SW35", 2)
    j(157, "DRB02_Ibracket", "C05", "M6SW35", 2)
    j(158, "DRB02_Ibracket", "C05", "M6SW35", 2)
    for i in range(4):
        j(159, f"Hanger_{i}_plate", "B03", "HANGER", 1)
    j(191, "Stake_C20_F", "C20_F", "SW50", 2)
    j(191, "Stake_C20_B", "C20_B", "SW50", 2)
    for st, e_, base, ft in NET_FIX:
        j(st, e_, base, ft, 1)

    return J
