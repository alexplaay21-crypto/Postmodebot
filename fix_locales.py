import json
from pathlib import Path

translations = {
    "ru": ["💾 Сохранённые посты","💾 Сохранить пост","✏️ Изменить текст","🖼 Изменить медиа","🔘 Изменить кнопки","🎯 Изменить канал","💾 Сохранённые посты","У тебя пока нет сохранённых постов.","Выбери пост:","💾 Введите название для сохранённого поста:","Название не может быть пустым. Введите название:","💾 Пост сохранён.","Пост не найден.","Пост удалён.","🗑 Удалить","◀️ К списку"],
    "en": ["💾 Saved posts","💾 Save post","✏️ Edit text","🖼 Edit media","🔘 Edit buttons","🎯 Edit channel","💾 Saved posts","You don't have any saved posts yet.","Choose a post:","💾 Enter a name for the saved post:","The name cannot be empty. Enter a name:","💾 Post saved.","Post not found.","Post deleted.","🗑 Delete","◀️ Back to list"],
    "es": ["💾 Publicaciones guardadas","💾 Guardar publicación","✏️ Editar texto","🖼 Editar multimedia","🔘 Editar botones","🎯 Editar canal","💾 Publicaciones guardadas","Todavía no tienes publicaciones guardadas.","Elige una publicación:","💾 Introduce un nombre para la publicación:","El nombre no puede estar vacío. Introduce un nombre:","💾 Publicación guardada.","Publicación no encontrada.","Publicación eliminada.","🗑 Eliminar","◀️ Volver a la lista"],
    "pt": ["💾 Posts salvos","💾 Salvar post","✏️ Editar texto","🖼 Editar mídia","🔘 Editar botões","🎯 Editar canal","💾 Posts salvos","Você ainda não tem posts salvos.","Escolha um post:","💾 Digite um nome para o post:","O nome não pode ficar vazio. Digite um nome:","💾 Post salvo.","Post não encontrado.","Post excluído.","🗑 Excluir","◀️ Voltar à lista"],
    "fr": ["💾 Publications enregistrées","💾 Enregistrer la publication","✏️ Modifier le texte","🖼 Modifier le média","🔘 Modifier les boutons","🎯 Modifier le canal","💾 Publications enregistrées","Vous n'avez pas encore de publications enregistrées.","Choisissez une publication :","💾 Entrez un nom pour la publication :","Le nom ne peut pas être vide. Entrez un nom :","💾 Publication enregistrée.","Publication introuvable.","Publication supprimée.","🗑 Supprimer","◀️ Retour à la liste"],
    "fa": ["💾 پست‌های ذخیره‌شده","💾 ذخیره پست","✏️ ویرایش متن","🖼 ویرایش رسانه","🔘 ویرایش دکمه‌ها","🎯 ویرایش کانال","💾 پست‌های ذخیره‌شده","هنوز هیچ پستی ذخیره نکرده‌اید.","یک پست را انتخاب کنید:","💾 یک نام برای پست وارد کنید:","نام نمی‌تواند خالی باشد. یک نام وارد کنید:","💾 پست ذخیره شد.","پست پیدا نشد.","پست حذف شد.","🗑 حذف","◀️ بازگشت به فهرست"],
    "ar": ["💾 المنشورات المحفوظة","💾 حفظ المنشور","✏️ تعديل النص","🖼 تعديل الوسائط","🔘 تعديل الأزرار","🎯 تعديل القناة","💾 المنشورات المحفوظة","لا توجد منشورات محفوظة لديك حتى الآن.","اختر منشورًا:","💾 أدخل اسمًا للمنشور:","لا يمكن أن يكون الاسم فارغًا. أدخل اسمًا:","💾 تم حفظ المنشور.","لم يتم العثور على المنشور.","تم حذف المنشور.","🗑 حذف","◀️ العودة إلى القائمة"],
    "hi": ["💾 सहेजी गई पोस्ट","💾 पोस्ट सहेजें","✏️ टेक्स्ट संपादित करें","🖼 मीडिया संपादित करें","🔘 बटन संपादित करें","🎯 चैनल संपादित करें","💾 सहेजी गई पोस्ट","आपके पास अभी कोई सहेजी गई पोस्ट नहीं है।","एक पोस्ट चुनें:","💾 पोस्ट का नाम दर्ज करें:","नाम खाली नहीं हो सकता। नाम दर्ज करें:","💾 पोस्ट सहेजी गई।","पोस्ट नहीं मिली।","पोस्ट हटा दी गई।","🗑 हटाएँ","◀️ सूची पर वापस"],
    "zh": ["💾 已保存的帖子","💾 保存帖子","✏️ 编辑文字","🖼 编辑媒体","🔘 编辑按钮","🎯 编辑频道","💾 已保存的帖子","你还没有保存任何帖子。","选择一条帖子：","💾 输入帖子的名称：","名称不能为空。请输入名称：","💾 帖子已保存。","未找到帖子。","帖子已删除。","🗑 删除","◀️ 返回列表"],
    "tg": ["💾 Паёмҳои захирашуда","💾 Захира кардани паём","✏️ Таҳрири матн","🖼 Таҳрири медиа","🔘 Таҳрири тугмаҳо","🎯 Таҳрири канал","💾 Паёмҳои захирашуда","Шумо ҳоло ягон паёми захирашуда надоред.","Паёмро интихоб кунед:","💾 Барои паём ном ворид кунед:","Ном холӣ буда наметавонад. Ном ворид кунед:","💾 Паём захира шуд.","Паём ёфт нашуд.","Паём нест карда шуд.","🗑 Нест кардан","◀️ Бозгашт ба рӯйхат"],
    "id": ["💾 Post tersimpan","💾 Simpan post","✏️ Edit teks","🖼 Edit media","🔘 Edit tombol","🎯 Edit kanal","💾 Post tersimpan","Kamu belum memiliki post tersimpan.","Pilih post:","💾 Masukkan nama untuk post:","Nama tidak boleh kosong. Masukkan nama:","💾 Post berhasil disimpan.","Post tidak ditemukan.","Post dihapus.","🗑 Hapus","◀️ Kembali ke daftar"],
    "ja": ["💾 保存した投稿","💾 投稿を保存","✏️ テキストを編集","🖼 メディアを編集","🔘 ボタンを編集","🎯 チャンネルを編集","💾 保存した投稿","保存した投稿はまだありません。","投稿を選択してください：","💾 投稿の名前を入力してください：","名前を空にすることはできません。名前を入力してください：","💾 投稿を保存しました。","投稿が見つかりません。","投稿を削除しました。","🗑 削除","◀️ 一覧に戻る"],
    "tr": ["💾 Kayıtlı gönderiler","💾 Gönderiyi kaydet","✏️ Metni düzenle","🖼 Medyayı düzenle","🔘 Butonları düzenle","🎯 Kanalı düzenle","💾 Kayıtlı gönderiler","Henüz kayıtlı gönderiniz yok.","Bir gönderi seçin:","💾 Gönderi için bir ad girin:","Ad boş olamaz. Bir ad girin:","💾 Gönderi kaydedildi.","Gönderi bulunamadı.","Gönderi silindi.","🗑 Sil","◀️ Listeye dön"],
    "de": ["💾 Gespeicherte Beiträge","💾 Beitrag speichern","✏️ Text bearbeiten","🖼 Medien bearbeiten","🔘 Buttons bearbeiten","🎯 Kanal bearbeiten","💾 Gespeicherte Beiträge","Du hast noch keine gespeicherten Beiträge.","Wähle einen Beitrag:","💾 Gib einen Namen für den Beitrag ein:","Der Name darf nicht leer sein. Gib einen Namen ein:","💾 Beitrag gespeichert.","Beitrag nicht gefunden.","Beitrag gelöscht.","🗑 Löschen","◀️ Zur Liste"],
    "fil": ["💾 Mga naka-save na post","💾 I-save ang post","✏️ I-edit ang text","🖼 I-edit ang media","🔘 I-edit ang mga button","🎯 I-edit ang channel","💾 Mga naka-save na post","Wala ka pang naka-save na post.","Pumili ng post:","💾 Maglagay ng pangalan para sa post:","Hindi maaaring walang laman ang pangalan. Maglagay ng pangalan:","💾 Na-save ang post.","Hindi nakita ang post.","Na-delete ang post.","🗑 Tanggalin","◀️ Bumalik sa listahan"],
    "ko": ["💾 저장된 게시물","💾 게시물 저장","✏️ 텍스트 수정","🖼 미디어 수정","🔘 버튼 수정","🎯 채널 수정","💾 저장된 게시물","아직 저장된 게시물이 없습니다.","게시물을 선택하세요:","💾 게시물 이름을 입력하세요:","이름은 비워둘 수 없습니다. 이름을 입력하세요:","💾 게시물이 저장되었습니다.","게시물을 찾을 수 없습니다.","게시물이 삭제되었습니다.","🗑 삭제","◀️ 목록으로"],
    "nl": ["💾 Opgeslagen berichten","💾 Bericht opslaan","✏️ Tekst bewerken","🖼 Media bewerken","🔘 Knoppen bewerken","🎯 Kanaal bewerken","💾 Opgeslagen berichten","Je hebt nog geen opgeslagen berichten.","Kies een bericht:","💾 Voer een naam in voor het bericht:","De naam mag niet leeg zijn. Voer een naam in:","💾 Bericht opgeslagen.","Bericht niet gevonden.","Bericht verwijderd.","🗑 Verwijderen","◀️ Terug naar lijst"],
    "it": ["💾 Post salvati","💾 Salva post","✏️ Modifica testo","🖼 Modifica media","🔘 Modifica pulsanti","🎯 Modifica canale","💾 Post salvati","Non hai ancora post salvati.","Scegli un post:","💾 Inserisci un nome per il post:","Il nome non può essere vuoto. Inserisci un nome:","💾 Post salvato.","Post non trovato.","Post eliminato.","🗑 Elimina","◀️ Torna alla lista"],
    "es_ar": ["💾 Publicaciones guardadas","💾 Guardar publicación","✏️ Editar texto","🖼 Editar multimedia","🔘 Editar botones","🎯 Editar canal","💾 Publicaciones guardadas","Todavía no tenés publicaciones guardadas.","Elegí una publicación:","💾 Escribí un nombre para la publicación:","El nombre no puede estar vacío. Escribí un nombre:","💾 Publicación guardada.","No se encontró la publicación.","Publicación eliminada.","🗑 Eliminar","◀️ Volver a la lista"],
    "th": ["💾 โพสต์ที่บันทึกไว้","💾 บันทึกโพสต์","✏️ แก้ไขข้อความ","🖼 แก้ไขสื่อ","🔘 แก้ไขปุ่ม","🎯 แก้ไขช่อง","💾 โพสต์ที่บันทึกไว้","ยังไม่มีโพสต์ที่บันทึกไว้","เลือกโพสต์:","💾 ป้อนชื่อสำหรับโพสต์:","ชื่อต้องไม่ว่าง โปรดป้อนชื่อ:","💾 บันทึกโพสต์แล้ว","ไม่พบโพสต์","ลบโพสต์แล้ว","🗑 ลบ","◀️ กลับไปที่รายการ"],
    "ur": ["💾 محفوظ شدہ پوسٹس","💾 پوسٹ محفوظ کریں","✏️ متن میں ترمیم","🖼 میڈیا میں ترمیم","🔘 بٹن میں ترمیم","🎯 چینل میں ترمیم","💾 محفوظ شدہ پوسٹس","آپ کے پاس ابھی کوئی محفوظ شدہ پوسٹ نہیں ہے۔","ایک پوسٹ منتخب کریں:","💾 پوسٹ کے لیے نام درج کریں:","نام خالی نہیں ہو سکتا۔ نام درج کریں:","💾 پوسٹ محفوظ ہو گئی۔","پوسٹ نہیں ملی۔","پوسٹ حذف کر دی گئی۔","🗑 حذف کریں","◀️ فہرست پر واپس"],
    "bn": ["💾 সংরক্ষিত পোস্ট","💾 পোস্ট সংরক্ষণ করুন","✏️ লেখা সম্পাদনা করুন","🖼 মিডিয়া সম্পাদনা করুন","🔘 বোতাম সম্পাদনা করুন","🎯 চ্যানেল সম্পাদনা করুন","💾 সংরক্ষিত পোস্ট","আপনার এখনও কোনো সংরক্ষিত পোস্ট নেই।","একটি পোস্ট বেছে নিন:","💾 পোস্টের জন্য একটি নাম লিখুন:","নাম খালি রাখা যাবে না। একটি নাম লিখুন:","💾 পোস্ট সংরক্ষণ করা হয়েছে।","পোস্ট পাওয়া যায়নি।","পোস্ট মুছে ফেলা হয়েছে।","🗑 মুছে ফেলুন","◀️ তালিকায় ফিরে যান"],
}

keys = [
    "menu_saved_posts",
    "btn_save_post",
    "btn_edit_text",
    "btn_edit_media",
    "btn_edit_buttons",
    "btn_edit_target",
    "saved_posts_title",
    "saved_posts_empty",
    "saved_posts_choose",
    "saved_post_name_prompt",
    "saved_post_name_empty",
    "saved_post_saved",
    "saved_post_not_found",
    "saved_post_deleted",
    "btn_saved_delete",
    "btn_saved_back",
]

for lang, values in translations.items():
    path = Path("locales") / f"{lang}.json"

    if not path.exists():
        raise SystemExit(f"MISSING FILE: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    for key, value in zip(keys, values):
        data[key] = value

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"{lang}: UPDATED")

print("\nCHECK:")

ok = True

for lang in translations:
    data = json.loads(
        (Path("locales") / f"{lang}.json").read_text(encoding="utf-8")
    )

    missing = [key for key in keys if key not in data]

    if missing:
        print(f"{lang}: MISSING {missing}")
        ok = False
    else:
        print(f"{lang}: OK")

if not ok:
    raise SystemExit("LOCALE CHECK FAILED")

print("\nALL 22 LOCALES OK")
