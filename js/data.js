  // BOTEN CR1016 Diesel Test Bench configuration data
  // 选项内容提取自 tb/CR1016/3-configs/ 下 PDF 清单

  const cr1016Categories = [
    {
      id: "cri",
      name: "CRI 共轨喷油器测试套件",
      description: "适配 Bosch、Delphi、CAT、Cummins、MTU、Denso 等共轨喷油器",
      multiple: true,
      options: [
        { id: "cri-1016", name: "BTK-1016 Injector Test Adapter", price: 0, description: "For CAT 320D C4/C6", image: "tb/tbconfig/CRI/BTK-1016.png" },
        { id: "cri-1017", name: "BTK-1017 Injector Test Adapter", price: 0, description: "For FOTON Cummins XPI", image: "tb/tbconfig/CRI/BTK-1017.png" },
        { id: "cri-1018", name: "BTK-1018 Injector Test Adapter", price: 0, description: "For Cummins XPI Scania", image: "tb/tbconfig/CRI/BTK-1018.png" },
        { id: "cri-1019", name: "BTK-1019 Injector Test Kit", price: 0, description: "For Bosch CRIN4.2 4-Pin<br><strong>BTK-1024 Control Unit is required</strong>", image: "tb/tbconfig/CRI/BTK-1019.png" },
        { id: "cri-1020", name: "BTK-1020 Injector Test Kit", price: 0, description: "For Delphi F2E 3+3", image: "tb/tbconfig/CRI/BTK-1020.jpg" },
        { id: "cri-1030", name: "BTK-1030 Injector Test Kit", price: 0, description: "For Delphi F2P-1", image: "tb/tbconfig/CRI/BTK-1030.png" },
        { id: "cri-1031", name: "BTK-1031 Injector Test Kit", price: 0, description: "For Delphi F2P-2", image: "tb/tbconfig/CRI/BTK-1031.png" },
        { id: "cri-1032", name: "BTK-1032 Injector Test Kit", price: 0, description: "For Delphi F2P-3", image: "tb/tbconfig/CRI/BTK-1032.png" },
        { id: "cri-1021", name: "BTK-1021 Injector Test Kit", price: 0, description: "For CAT C9.3", image: "tb/tbconfig/CRI/BTK-1021.png" },
        { id: "cri-1034", name: "BTK-1034 Injector Test Adapter", price: 0, description: "For MTU-2000", image: "tb/tbconfig/CRI/BTK-1034.png" },
        { id: "cri-1035", name: "BTK-1035 Injector Test Kit", price: 0, description: "For MTU-4000", image: "tb/tbconfig/CRI/BTK-1035.png" },
        { id: "cri-1036", name: "BTK-1036 Injector Test Kit", price: 0, description: "For Cummins QSK19", image: "tb/tbconfig/CRI/BTK-1036.png" },
        { id: "cri-1146", name: "BTE-1146 Test Cable", price: 0, description: "For Denso IART G4 6 Pin", image: "tb/tbconfig/CRI/BTE-1146.jpg" }
      ]
    },
    {
      id: "heui",
      name: "HEUI 中压喷油器适配器",
      description: "适配 CAT、ISUZU、NAVISTAR、Ford 等HEUI喷油器",
      multiple: true,
      options: [
        { id: "heui-c7c9", name: "BTE-7021 CAT C7/C9 Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7021.jpg" },
        { id: "heui-3126b", name: "BTE-7024 CAT 3126B Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7024.jpg" },
        { id: "heui-3412e", name: "BTE-7058 CAT 3412E Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7058.jpg" },
        { id: "heui-3126a", name: "BTE-7078 CAT 3126A Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7078.jpg" },
        { id: "heui-isuzu", name: "BTE-7069 ISUZU Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7069.jpg" },
        { id: "heui-navistar", name: "BTE-7022 NAVISTAR Adapter", price: 0, description: "", image: "tb/tbconfig/HEUI/BTE-7022.jpg" },
        { id: "heui-g28", name: "BTE-7048 Ford G2.8 Adapter", price: 0, description: "<strong>BTK-1024 Control Unit is required</strong>", image: "tb/tbconfig/HEUI/BTE-7048.jpg" },
        { id: "heui-g29", name: "BTE-7030 Ford G2.9 Adapter", price: 0, description: "<strong>BTK-1024 Control Unit is required</strong>", image: "tb/tbconfig/HEUI/BTE-7030.jpg" }
      ]
    },
    {
      id: "eui-eup",
      name: "EUI/EUP Adapter凸轮箱",
      description: "适配 Delphi、Bosch、Cummins、CAT、SCANIA、IVECO、Detroit、Volkswagen 等EUI EUP测试",
      multiple: true,
      options: [
        { id: "eui-ae1e3", name: "BTE-4240 Delphi A / E1 / E3 Adapter", price: 0, description: "Cam: BTE-0006/0004 | Collector: BTE-4023/4152 | Rod: BTE-020 | Cable: AE66/4 AE66/9" },
        { id: "eui-m11n14", name: "BTE-4161 Cummins M11 / N14 Adapter", price: 0, description: "Cam: BTE-4163 | Collector: BTE-4160 | Rod: BTE-011 | Cable: M11" },
        { id: "eui-c12", name: "BTE-4032 CAT C12 Adapter", price: 0, description: "Cam: BTE-0007 | Collector: BTE-4033 | Rod: BTE-013 | Cable: AE66/5" },
        { id: "eui-c13c15c18", name: "BTE-4035 CAT C13 / C15 / C18 Adapter", price: 0, description: "Cam: BTE-0006 | Collector: BTE-4033 | Rod: BTE-013 | Cable: AE66/5 349EC13" },
        { id: "eui-3512b", name: "BTE-4447 CAT 3512B Adapter", price: 0, description: "Cam: BTE-0006 | Collector: BTE-4441 | Rod: BTE-013 | Cable: AE66/5" },
        { id: "eui-scania", name: "BTE-4131 SCANIA Adapter", price: 0, description: "Cam: BTE-0006 | Collector: BTE-4132 | Rod: BTE-015 | Cable: AE66/2" },
        { id: "eui-iveco8", name: "BTE-4042 IVECO 8 Adapter", price: 0, description: "Cam: BTE-0011 | Collector: BTE-4043 | Rod: BTE-022 | Cable: AE66/2" },
        { id: "eui-iveco1013", name: "BTE-4052 IVECO 10/13 Adapter", price: 0, description: "Cam: BTE-0006 | Collector: BTE-4043 | Rod: BTE-013 | Cable: AE66/2" },
        { id: "eui-n2", name: "BTE-4069 Detroit N2 Adapter", price: 0, description: "Cam: BTE-0006 | Collector: BTE-4058 | Rod: BTE-014 | Cable: AE66/10" },
        { id: "eui-n3", name: "BTE-4300 Detroit N3 Adapter", price: 0, description: "Cam: BTE-0004 | Collector: BTE-4023 | Rod: BTE-013 | Cable: AE66/4" },
        { id: "eui-nissan", name: "BTE-4305 NISSAN Adapter", price: 0, description: "Cam: BTE-0004 | Collector: BTE-4306 | Rod: BTE-020 | Cable: AE66/2" },
        { id: "eui-ppd", name: "BTE-4170 Volkswagen PPD Adapter", price: 0, description: "Cam: BTE-4010X | Collector: BTE-4171 | Rod: BTE-022 | Cable: AE66/13" },
        { id: "eui-td5", name: "BTE-4141 Land Rover TD5 Adapter", price: 0, description: "Cam: BTE-4010X | Collector: BTE-4023 | Rod: BTE-018 | Cable: AE66/6" },
        { id: "eui-pd", name: "BTE-4112 Volkswagen PD Adapter", price: 0, description: "Cam: BTE-4010X | Collector: BTE-4023 | Rod: BTE-018 | Cable: AE66/11" },
        { id: "eui-pdb", name: "BTE-4178 Volkswagen PDB Adapter", price: 0, description: "Cam: BTE-4010X | Collector: BTE-4171 | Rod: BTE-018 | Cable: AE66/11" },
        { id: "eui-nanyue", name: "BTE-302 NANYUE Engineering Machinery Adapter", price: 0, description: "Cam: BTE-0007 | Collector: EUP Standard Injector | Rod: BTE-030 | Cable: AE66/11" },
        { id: "eui-3116", name: "BTE-121 CAT 3116 Adapter", price: 0, description: "Cam: BTE-0011 | Collector: BTE-121 | Rod: BTE-014 | Cable: rack type, no cable" },
        { id: "eui-3512a", name: "BTE-141 CAT 3512A Adapter", price: 0, description: "Cam: BTE-0011 | Collector: BTE-4441 | Rod: BTE-014 | Cable: rack type, no cable" },
        { id: "eui-n1gm", name: "BTE-190 Detroit N1 / GM Adapter", price: 0, description: "Cam: BTE-4010X | Collector: BTE-190 | Rod: BTE-019 | Cable: rack type, no cable" },
        { id: "eui-actros", name: "BTE-4084 Benz ACTROS Adapter", price: 0, description: "Cam: BTE-0001 | Collector: EUP Standard Injector | Rod: BTE-021 | Cable: AE66/2" },
        { id: "eui-atego", name: "BTE-4079 Benz ATEGO Adapter", price: 0, description: "Cam: BTE-0007 | Collector: EUP Standard Injector | Rod: BTE-021/023 | Cable: AE66/2" },
        { id: "eui-daf", name: "BTE-4405 Delphi DAF Adapter", price: 0, description: "Cam: BTE-0001 | Collector: EUP Standard Injector | Rod: BTE-013 | Cable: AE66/4" },
        { id: "eui-liebherr", name: "BTE-4096 LIEBHERR Adapter", price: 0, description: "Cam: BTE-0001 | Collector: EUP Standard Injector | Rod: BTE-013 | Cable: AE66/4" },
        { id: "eui-weite-eup", name: "BTE-300 WEITE EUP Adapter", price: 0, description: "Cam: BTE-0007 | Collector: EUP Standard Injector | Rod: BTE-030 | Cable: AE66/11" },
        { id: "eui-weite-hengyang", name: "BTE-301 WEITE / HENGYANG / Delphi Adapter", price: 0, description: "Cam: BTE-0006 | Collector: EUP Standard Injector | Rod: BTE-030 | Cable: AE66/2 AE66/4" }
      ]
    },
    {
      id: "crp",
      name: "CRP 共轨泵工装测试套件",
      description: "适配 PT 泵、CAT、Cummins XPI、Bosch、Denso、MTU、Liebherr 等特殊共轨泵",
      multiple: true,
      options: [
        { id: "crp-1027", name: "BTK-1027 Cummins PT Fuel Pump Test Kit", price: 0, description: "PT Fuel Pump Test Kit on CR1016" },
        { id: "crp-1099", name: "BTK-1099 Multi-Model Pump Test Kit", price: 0, description: "For CR1018 / CR918S / CR1016" },
        { id: "crp-1001", name: "BTK-1001 Universal Pump Test Kit", price: 0, description: "For common pump test kits" },
        { id: "crp-1002", name: "BTK-1002 CAT 336E C9.3 Pump Test Kit", price: 0, description: "CAT 336E C9.3 Pump" },
        { id: "crp-1003", name: "BTK-1003 Cummins XPI / FOTON Pump Test Kit", price: 0, description: "Cummins XPI / FOTON" },
        { id: "crp-1004", name: "BTK-1004 Bosch CB28 Pump Test Kit", price: 0, description: "Bosch CB28 Pump" },
        { id: "crp-1005", name: "BTK-1005 HP5 / HP6 Pump Test Kit", price: 0, description: "HP5 / HP6 Pump" },
        { id: "crp-1006", name: "BTK-1006 HP7 / CCR1600 / CPN5 / CP4.2 / CP2 Pump Test Kit", price: 0, description: "Denso HP7 / Cummins CCR1600 / Bosch CPN5 CP4.2 CP2" },
        { id: "crp-1007", name: "BTK-1007 MTU-2000 Pump Test Kit", price: 0, description: "MTU-2000 Pump" },
        { id: "crp-1008", name: "BTK-1008 MTU-4000 Pump Test Kit", price: 0, description: "MTU-4000 Pump" },
        { id: "crp-1009", name: "BTK-1009 Cummins QSK19 / CP9 Pump Test Kit", price: 0, description: "Cummins QSK19 / CP9 Pump" },
        { id: "crp-1010", name: "BTK-1010 Yangtzc Pump Test Kit", price: 0, description: "Yangtzc Pump" },
        { id: "crp-1011", name: "BTK-1011 Cummins M11 Pump Test Kit", price: 0, description: "Cummins M11 Pump" },
        { id: "crp-1012", name: "BTK-1012 Liebherr Pump Test Kit 1", price: 0, description: "Liebherr Pump 1" },
        { id: "crp-1013", name: "BTK-1013 Liebherr Pump Test Kit 2", price: 0, description: "Liebherr Pump 2" },
        { id: "crp-1014", name: "BTK-1014 Cummins XPI / Scania Pump Test Kit", price: 0, description: "Cummins XPI / Scania Pump" },
        { id: "crp-1015", name: "BTK-1015 CAT 320D Pump Test Kit", price: 0, description: "CAT 320D Pump" },
        { id: "crp-1029", name: "BTK-1029 Denso HP0 / CP3 / CP2.2 / XPI Pump Test Kit", price: 0, description: "Denso HP0 CP3 / New CP2.2 / Cummins XPI" }
      ]
    },
    {
      id: "extension",
      name: "Cambox Extension 凸轮箱扩展功能",
      description: "扩展E3控制单元、HPI喷油器、PT 喷油器、F2P/F2E 等测试能力",
      multiple: true,
      options: [
        { id: "ext-1024", name: "BTK-1024 E3 Control Unit", price: 0, description: "For Dehphi E3 EUI / HPI Injector / Bosch CRIN 4.2 / HEUI FORD G2.X" },
        { id: "ext-1025", name: "BTK-1025 HPI Q60X15 Test Kit", price: 0, description: "HPI Q60 X15 Test Kit" },
        { id: "ext-1026", name: "BTK-1026 PT Series Fuel Injector Test Kit", price: 0, description: "PT Series Fuel Injector Test Kit" },
        { id: "ext-1028", name: "BTK-1028 F2P Pump F2E Pumping Test Kit", price: 0, description: "F2P Unit Pump / F2E Pumping Test Kit" }
      ]
    }
  ];

  // 转录自 tb/tblist.xls
  const tbListData = [
    {
      id: 1,
      type: "BOTEN CR1016",
      name: "Multifunctional Test Bench",
      colors: ["Green", "Red"],
      motors: ["22kw Servo Motor"],
      voltages: ["Default 380V 3Phase", "External Convrter 220V 3Phase"],
      configs: ["CRI", "HEUI", "CRP", "Cambox EUi EUP", "Cambox Extention"],
      detailImages: []
    },
    {
      id: 2,
      type: "BOTEN CR518",
      name: "EUi EUP Test Bench",
      colors: ["Green"],
      motors: ["11kw Servo Motor"],
      voltages: ["Default 380V 3Phase", "External Convrter 220V 3Phase"],
      configs: ["Cambox EUi EUP", "Cambox Extention"],
      detailImages: ["CR518.png"]
    },
    {
      id: 6,
      type: "BOTEN CR318 PRO",
      name: "4 Channel CRI Test Bench",
      colors: ["Green"],
      motors: ["5.5kw Inverter Motor"],
      voltages: ["Default 380V 3Phase"],
      configs: ["CRI"],
      detailImages: []
    },
    {
      id: 3,
      type: "BOTEN CR318S",
      name: "CRI & HEUI Injector Test Bench",
      colors: ["Green"],
      motors: ["4.5kw Inverter Motor"],
      voltages: ["Default 380V 3Phase"],
      configs: ["CRI", "HEUI"],
      detailImages: ["CR318S.png"]
    },
    {
      id: 4,
      type: "BOTEN CR318C",
      name: "CRI Injector Test Bench",
      colors: ["Green"],
      motors: ["4.5kw Inverter Motor"],
      voltages: ["Default 380V 3Phase", "Inverter 220V 3Phase"],
      configs: ["CRI"],
      detailImages: ["CR318C.png"]
    },
    {
      id: 5,
      type: "BOTEN CR318H",
      name: "HEUI Injector Test Bench",
      colors: ["Green"],
      motors: ["4.5kw Inverter Motor"],
      voltages: ["Default 380V 3Phase", "Inverter 220V 3Phase"],
      configs: ["HEUI"],
      detailImages: ["CR318H.png"]
    },
    {
      id: 7,
      type: "BOTEN BT618",
      name: "Mechanical Pump Test Bench",
      colors: ["Green"],
      motors: ["22kw Servo Motor", "11kw Servo Motor"],
      voltages: ["Default 380V 3Phase", "External Convrter 220V 3Phase"],
      configs: ["BT618 Extension"],
      detailImages: [
        "BT618.png",
        "1de61363f7c46438ae4ff87f8b25de44.jpg",
        "520e437c31f60934eb60398c02015470.jpg",
        "9e758c17691fb039df03362b2cac1003.jpg",
        "c074c1627924b6a9519af3df761c847f.jpg",
        "f62b87482dd7447f54d983d1c1ece3e3.jpg",
        "f6788e90e6eebf158e84bc07a282d6ea.jpg"
      ]
    }
  ];

  // 每个机型的可选配置在这里单独维护。
  // 数组中只保存公共配置库 cr1016Categories 里的选项 id，图片和基础文案仍可复用。
  // overrides 可覆盖特定机型上的文案、价格或图片，避免修改公共配置影响其他机型。
  const modelOptionMappings = {
    cr1016: {
      cri: ["cri-1016", "cri-1017", "cri-1018", "cri-1019", "cri-1020", "cri-1030", "cri-1031", "cri-1032", "cri-1021", "cri-1034", "cri-1035", "cri-1036", "cri-1146"],
      heui: ["heui-c7c9", "heui-3126b", "heui-3412e", "heui-3126a", "heui-isuzu", "heui-navistar", "heui-g28", "heui-g29"],
      crp: ["crp-1027", "crp-1099", "crp-1001", "crp-1002", "crp-1003", "crp-1004", "crp-1005", "crp-1006", "crp-1007", "crp-1008", "crp-1009", "crp-1010", "crp-1011", "crp-1012", "crp-1013", "crp-1014", "crp-1015", "crp-1029"],
      "eui-eup": ["eui-ae1e3", "eui-m11n14", "eui-c12", "eui-c13c15c18", "eui-3512b", "eui-scania", "eui-iveco8", "eui-iveco1013", "eui-n2", "eui-n3", "eui-nissan", "eui-ppd", "eui-td5", "eui-pd", "eui-pdb", "eui-nanyue", "eui-3116", "eui-3512a", "eui-n1gm", "eui-actros", "eui-atego", "eui-daf", "eui-liebherr", "eui-weite-eup", "eui-weite-hengyang"],
      extension: ["ext-1024", "ext-1025", "ext-1026", "ext-1028"]
    },
    cr518: {
      "eui-eup": ["eui-ae1e3", "eui-m11n14", "eui-c12", "eui-c13c15c18", "eui-3512b", "eui-scania", "eui-iveco8", "eui-iveco1013", "eui-n2", "eui-n3", "eui-nissan", "eui-ppd", "eui-td5", "eui-pd", "eui-pdb", "eui-nanyue", "eui-3116", "eui-3512a", "eui-n1gm", "eui-actros", "eui-atego", "eui-daf", "eui-liebherr", "eui-weite-eup", "eui-weite-hengyang"],
      // BTK-1028 不适用于 CR518，因此不列入该数组。
      extension: ["ext-1024", "ext-1025", "ext-1026"]
    },
    cr318pro: {
      cri: ["cri-1016", "cri-1017", "cri-1018", "cri-1019", "cri-1020", "cri-1030", "cri-1031", "cri-1032", "cri-1021", "cri-1034", "cri-1035", "cri-1036", "cri-1146"]
    },
    cr318s: {
      cri: ["cri-1016", "cri-1017", "cri-1018", "cri-1019", "cri-1020", "cri-1030", "cri-1031", "cri-1032", "cri-1021", "cri-1034", "cri-1035", "cri-1036", "cri-1146"],
      heui: ["heui-c7c9", "heui-3126b", "heui-3412e", "heui-3126a", "heui-isuzu", "heui-navistar", "heui-g28", "heui-g29"]
    },
    cr318c: {
      cri: ["cri-1016", "cri-1017", "cri-1018", "cri-1019", "cri-1020", "cri-1030", "cri-1031", "cri-1032", "cri-1021", "cri-1034", "cri-1035", "cri-1036", "cri-1146"]
    },
    cr318h: {
      heui: ["heui-c7c9", "heui-3126b", "heui-3412e", "heui-3126a", "heui-isuzu", "heui-navistar", "heui-g28", "heui-g29"]
    },
    bt618: {
      extension: ["ext-1024", "ext-1025", "ext-1026", "ext-1028"]
    }
  };

  const modelOptionOverrides = {
    cr318pro: { "cri-1019": { description: "For Bosch CRIN4.2 4-Pin" } },
    cr318s: { "cri-1019": { description: "For Bosch CRIN4.2 4-Pin" } },
    cr318c: { "cri-1019": { description: "For Bosch CRIN4.2 4-Pin" } }
  };

  function colorToCn(color) {
    const map = {
      "Green": "绿色",
      "Red": "红色",
      "Amber": "琥珀色"
    };
    return map[color] || color;
  }

  function resolveMainImages(model, color) {
    if (model.colorImages?.[color]) {
      return [model.colorImages[color]];
    }
    const code = model.type.replace(/^BOTEN\s+/i, "").trim();
    if (model.colors.length > 1 && color) {
      return [`tb/tbpic/${code}/${code}${colorToCn(color)}.png`];
    }
    return [`tb/tbpic/${code}/${code}.png`];
  }

  function resolveDetailImages(model) {
    const code = model.type.replace(/^BOTEN\s+/i, "").trim();
    return (model.detailImages || []).map((filename) => `tb/tbdetail/${code}/${filename}`);
  }

  function resolveGalleryImages(model, color) {
    return [...resolveMainImages(model, color), ...resolveDetailImages(model)];
  }

  function buildSpecCategory(id, name, values) {
    return {
      id,
      name,
      description: "",
      multiple: false,
      options: values.map((value, idx) => ({
        id: `${id}-${idx}`,
        name: value,
        price: 0,
        description: ""
      }))
    };
  }

  function buildModelCategories(tb, modelId) {
    const categories = [];

    categories.push(buildSpecCategory("motor", "电机选择", tb.motors));
    categories.push(buildSpecCategory("voltage", "供电选择", tb.voltages));

    const mapping = modelOptionMappings[modelId] || {};
    const overrides = modelOptionOverrides[modelId] || {};
    const configCategories = Object.entries(mapping).map(([categoryId, optionIds]) => {
      const source = cr1016Categories.find((category) => category.id === categoryId);
      if (!source) return null;

      const options = optionIds.map((optionId) => {
        const sourceOption = source.options.find((option) => option.id === optionId);
        if (!sourceOption) {
          console.warn(`Unknown option mapping: ${modelId}-${categoryId}-${optionId}`);
          return null;
        }

        const optionCode = sourceOption.name.split(/\s+/)[0].replace(/-/g, "").toUpperCase();
        return {
          ...sourceOption,
          ...(overrides[optionId] || {}),
          mappingId: `${modelId.toUpperCase()}-${categoryId.toUpperCase()}-${optionCode}`
        };
      }).filter(Boolean);

      return { ...source, options };
    }).filter(Boolean);

    categories.push(...configCategories);
    return categories;
  }

  function buildModelId(type) {
    return type.replace(/^BOTEN\s+/i, "").replace(/\s+/g, "").toLowerCase();
  }

  function getDefaultColor(model) {
    return model.colors.includes("Green") ? "Green" : model.colors[0];
  }

  const configData = {
    models: tbListData.map((tb) => {
      const modelId = buildModelId(tb.type);
      return {
        id: modelId,
        name: tb.type,
        type: tb.type,
        titleName: tb.name,
        colors: tb.colors,
        detailImages: tb.detailImages || [],
        basePrice: 0,
        description: "设备描述XXXX占位",
        categories: buildModelCategories(tb, modelId)
      };
    })
  };

  function getModelById(id) {
    return configData.models.find((m) => m.id === id) || null;
  }

  function getDefaultSelections(model) {
    const selections = {};
    model.categories.forEach((cat) => {
      const isBuiltInSingleChoice = cat.id === "motor" || cat.id === "voltage";
      if (cat.multiple && !isBuiltInSingleChoice) {
        // A section with only one possible choice should already be selected.
        selections[cat.id] = cat.options.length === 1 ? [cat.options[0].id] : [];
      } else {
        selections[cat.id] = cat.options[0]?.id || null;
      }
    });
    return selections;
  }
