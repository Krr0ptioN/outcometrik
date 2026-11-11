from rest_framework import serializers


class ExportQuerySerializer(serializers.Serializer):
    publication_id = serializers.UUIDField()
    format = serializers.ChoiceField(choices=("csv", "pdf"))
    scope = serializers.ChoiceField(choices=("student", "cohort"))
    program_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if attrs["scope"] == "cohort" and "program_id" not in attrs:
            raise serializers.ValidationError({"program_id": "This field is required."})
        if attrs["scope"] == "student" and "program_id" in attrs:
            raise serializers.ValidationError({"program_id": "Not accepted for a student export."})
        return attrs
