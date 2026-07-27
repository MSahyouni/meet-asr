// class VoiceModel {
//   final String id;
//   final String name;

//   VoiceModel({required this.id, required this.name});

//   factory VoiceModel.fromJson(Map<String, dynamic> json) {
//     return VoiceModel(id: json['id'], name: json['name']);
//   }
// }

class VoiceModel {
  final String id;
  final String name;

  VoiceModel({required this.id, required this.name});

  factory VoiceModel.fromDynamic(dynamic json) {
    // إذا رجع String مثل "habibi_unified"
    if (json is String) {
      return VoiceModel(id: json, name: json);
    }

    // إذا رجع Map مثل {"id":"x","name":"y"} أو {"voice":"x"}
    if (json is Map<String, dynamic>) {
      final id = (json['id'] ?? json['voice'] ?? json['value'] ?? '')
          .toString();
      final name = (json['name'] ?? json['label'] ?? id).toString();
      return VoiceModel(id: id, name: name);
    }

    // fallback
    return VoiceModel(id: json.toString(), name: json.toString());
  }
}
