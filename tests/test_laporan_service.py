from datetime import date

from src.services.LaporanService import LaporanService


class FakeLaporanDb:
    """Answers every query LaporanService issues, matched on a distinctive fragment of its SQL.

    Keep the fragments in sync with the SQL in LaporanService: if a query is not recognised the
    fake returns [] and the service reports "Tidak ada data" (this is how the produk_id rename
    broke the test before).
    """

    def execute_query(self, sql, params=None):
        normalized = " ".join(sql.split()).lower()

        if "count(distinct ph.produk_id)" in normalized:  # ringkasan: produksi
            return [{"total_aktual": 300, "hari_kerja": 6, "jumlah_produk": 3}]
        if "as total_defect" in normalized:  # ringkasan: total defect
            return [{"total_defect": 15}]
        if "as total_target" in normalized:  # ringkasan: total target
            return [{"total_target": 360}]
        if "produksi.total_produksi" in normalized:  # defect per bulan
            return [{"bulan": date(2026, 4, 1), "total_produksi": 300, "jumlah_defect": 15}]
        if "as aktual" in normalized and "group by bulan" in normalized:  # pencapaian per bulan
            return [{"bulan": date(2026, 4, 1), "aktual": 300}]
        if "as target" in normalized:  # target satu bulan
            return [{"target": 360}]
        if "join produksi_harian ph on ph.produk_id = p.produk_id" in normalized and "group by" in normalized:
            return [
                {"nama_produk": "Kaos", "aktual": 180},
                {"nama_produk": "Kemeja", "aktual": 120},
            ]
        if "from tipe_defect td" in normalized:
            return [
                {"nama_defect": "Kecacatan Fisik", "jumlah": 10},
                {"nama_defect": "Kesalahan Proses", "jumlah": 5},
            ]
        return []  # e.g. kendala produksi: none


class EmptyLaporanDb:
    def execute_query(self, sql, params=None):
        normalized = " ".join(sql.split()).lower()
        if "count(distinct ph.produk_id)" in normalized:
            return [{"total_aktual": 0, "hari_kerja": 0, "jumlah_produk": 0}]
        return []


def test_generate_laporan_menolak_range_tanggal_tidak_valid():
    service = LaporanService(db=FakeLaporanDb())

    result = service.generate_laporan(date(2026, 5, 10), date(2026, 5, 1))

    assert result["success"] is False
    assert result["filepath"] is None
    assert "Tanggal mulai" in result["message"]


def test_generate_laporan_gagal_jika_tidak_ada_data():
    service = LaporanService(db=EmptyLaporanDb())

    result = service.generate_laporan(date(2026, 5, 1), date(2026, 5, 10))

    assert result["success"] is False
    assert "Tidak ada data" in result["message"]


def test_generate_laporan_berhasil_dengan_db_fake(monkeypatch):
    service = LaporanService(db=FakeLaporanDb())

    monkeypatch.setattr(service, "_build_html", lambda data: "<html>ok</html>")
    monkeypatch.setattr(service, "_export_pdf", lambda html, awal, akhir, output_dir: "doc/laporan_test.pdf")

    result = service.generate_laporan(date(2026, 4, 1), date(2026, 4, 30), dicetak_oleh="Tester")

    assert result["success"] is True
    assert result["filepath"] == "doc/laporan_test.pdf"
    assert result["data"]["ringkasan"]["total_aktual"] == 300
    assert result["data"]["ringkasan"]["defect_rate"] == 5.0
    assert result["data"]["pencapaian_bulanan"][0]["efisiensi"] == 83.3
